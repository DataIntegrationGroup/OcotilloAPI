"""add the water well field operations layer

An internal-only OGC layer for field crews: one row per water well, carrying
what a crew needs to plan and execute a visit -- where the well is, who owns it
and how to reach them, what the crew is permitted to do there, what is
installed in it, and when it was last measured. Every other well layer answers
a scientific question; this one answers an operational one.

Two relations, not one:

    ogc_internal_water_well_field_operations_stats   MATERIALIZED VIEW
        Counts, first/last dates and aggregates over `observation` and
        `transducer_observation`. Expensive, refreshed nightly by the pg_cron
        job (b6c7d8e9f0a1), which discovers matviews from the catalog and so
        needs no schedule change.

    ogc_internal_water_well_field_operations        VIEW  <- pygeoapi reads this
        Live join of thing, location, status_history, permission_history,
        measuring_point_history, monitoring_frequency_history, deployment,
        sensor, contact and notes, LEFT JOINed to the stats matview.

The split is not tidiness. Staleness is dangerous on exactly the columns that
are cheap to read: a revoked sampling permission that still reads `true` until
the next nightly refresh sends a crew onto land they are no longer welcome on.
And the current-record rule below is written against CURRENT_DATE, which in a
materialized view would freeze at refresh time -- a permission that expired
this morning would still read current tonight. Those columns have to be in the
plain view.

Internal only, and deliberately without a public twin: the layer publishes
landowner contact details and staff-written access notes.
`ogc_water_well_field_operations` does not exist and must never be created. The
parity guard in tests/test_migration_view_parity.py reads two named migration
files (f4a5b6c7d8e9 and 2d3c3a268652) and is unaffected by a relation created
here.

Current-record rule, applied identically to all four history tables
(status_history, permission_history, measuring_point_history,
monitoring_frequency_history):

    start_date <= CURRENT_DATE
    AND (end_date IS NULL OR end_date >= CURRENT_DATE)
    ORDER BY start_date DESC, id DESC   -- via DISTINCT ON

This diverges from ogc_actively_monitored_wells, which takes the greatest
start_date and ignores end_date entirely, so a status closed in 2019 still
reads as current there. Tolerable on a summary layer; not on one whose job is
to say what is true today. See docs/ogc_conventions.md.

The three permission columns are three-valued and must stay that way: true =
a current grant says allowed, false = a current grant says not allowed, NULL =
no permission on record. NULL is not "denied" -- it means nobody has asked the
landowner yet.

Depth to water uses (value - COALESCE(measuring_point_height, 0)) -- the
reading minus the height of the measuring point above ground, a missing height
treated as ground level. Character-for-character the convention in
ogc_water_well_summary, ogc_latest_depth_to_water_wells and
ogc_well_water_column, so the four layers cannot disagree about what a depth to
water is.

Multi-valued columns are emitted as comma-joined text rather than as arrays
(which ogc_actively_monitored_wells uses). This layer exists to be pulled into
ArcGIS Pro and QGIS and exported to a File Geodatabase or GeoPackage for
offline field use, and neither format has a list type.

Both relations are new here, so downgrade() drops them rather than restoring a
prior state. The supporting indexes are also created here: none of these
foreign keys was indexed (Postgres does not index foreign keys on its own).

Consolidated from two independently-drafted layers (this one and
kas-water-well-operations-ogc-layer-bdms-1202) after a side-by-side review.
The deltas from the version that first merged (3499f414):

- Dropped: nma_pk_welldata, county, state, quad_name, elevation_method (and
  its data_provenance LATERAL lookup, now unused), nma_formation_zone,
  measuring_point_start_date, and every `*_since`/`*_reason` status and
  monitoring-frequency column. access_status itself is also dropped (not just
  its `_since` companion): status_value has no terms scoped to Access Status
  in the lexicon, so the column could only ever read NULL, and access_notes
  already carries staff-written access information for a well.
- Renamed to match the naming already established on the public thing-type
  views: thing_type -> station_type, well_casing_materials ->
  well_casing_material, well_purposes -> well_purpose,
  measuring_point_height/measuring_point_description -> mp_height/
  mp_description, field_event_last_date (from the stats matview) ->
  date_last_visited.
- Added formation_completion_description (lexicon_term.definition for the
  term named by formation_completion_code) and aquifer_system_name
  (thing_aquifer_association -> aquifer_system, comma-joined), both scalar
  lookups with no date-window semantics of their own -- neither source table
  carries a start_date/end_date.
- Broadened "currently installed equipment" from logger-only to every
  currently-installed sensor. The original datalogger_sensor_type/model/
  serial_no/sensor_status/installed_date/recording_interval/
  recording_interval_units/hanging_point_description picked a single row
  (DISTINCT ON, most-recently-installed) from deployments filtered to
  LOGGER_SENSOR_TYPES, so a currently-installed camera or barometer was
  invisible. The unprefixed sensor_type/model/serial_no/sensor_status/
  installed_date/recording_interval/recording_interval_units/
  hanging_point_desc columns now aggregate every currently-installed sensor
  regardless of type (semicolon-joined, ordered by sensor_type, same
  convention as the comma-joined columns above but semicolon because these
  are genuinely positional -- position N in one list is the same deployment as
  position N in the others). has_datalogger/datalogger_deployment_count stay
  logger-scoped exactly as before, for whoever specifically needs "is this
  well instrumented," now computed from the broader deployment set filtered
  inline rather than a separate pre-filtered CTE.
- Added one column per notes.note_type value (13 total, including the
  pre-existing access_notes/directions_notes), `_notes`-suffixed, same
  string_agg(' | ', id DESC) pattern as the original two. `OwnerComment` ->
  owner_comment_notes and `Site Notes (legacy)` -> site_notes_legacy are the
  two that do not mechanically snake-case; the legacy one is not
  double-suffixed since the term already says "notes".

Revision ID: e1f2a3b4c5d6
Revises: c9d0e1f2a3b4
Create Date: 2026-08-31 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "location",
    "location_thing_association",
    "observation",
    "sample",
    "field_activity",
    "field_event",
    "status_history",
    "permission_history",
    "measuring_point_history",
    "monitoring_frequency_history",
    "deployment",
    "sensor",
    "transducer_observation",
    "contact",
    "thing_contact_association",
    "phone",
    "email",
    "notes",
    "group",
    "group_thing_association",
    "well_purpose",
    "well_casing_material",
    "well_screen",
    "thing_id_link",
    "lexicon_term",
    "thing_aquifer_association",
    "aquifer_system",
}

STATS_VIEW = "ogc_internal_water_well_field_operations_stats"
FEATURE_VIEW = "ogc_internal_water_well_field_operations"

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()

# sensor_type values that mean "this well is logging by itself". Anything else
# deployed at a well (a barometer, a camera) is equipment, not a logger, and
# must not make has_datalogger true.
LOGGER_SENSOR_TYPES = (
    "'Data Logger'",
    "'Pressure Transducer'",
    "'DiverLink'",
    "'Diver Cable'",
)

# notes.note_type -> published column name. Order matches core/lexicon.json's
# note_type category. Two do not mechanically snake-case: OwnerComment has no
# separator to split on, and "Site Notes (legacy)" already says "notes" so it
# is not double-suffixed.
NOTE_TYPES = (
    ("Access", "access_notes"),
    ("Directions", "directions_notes"),
    ("Communication", "communication_notes"),
    ("Construction", "construction_notes"),
    ("Maintenance", "maintenance_notes"),
    ("Historical", "historical_notes"),
    ("General", "general_notes"),
    ("Water", "water_notes"),
    ("Water Quality", "water_quality_notes"),
    ("Sampling Procedure", "sampling_procedure_notes"),
    ("Coordinate", "coordinate_notes"),
    ("OwnerComment", "owner_comment_notes"),
    ("Site Notes (legacy)", "site_notes_legacy"),
)

# Indexes the per-well lookups need. Each is created IF NOT EXISTS: none of
# these existed when this migration was written, but the thing_type one in
# particular is the sort of thing another migration may add first.
SUPPORTING_INDEXES = [
    (
        "ix_status_history_target_type_start",
        "status_history (target_table, target_id, status_type, start_date DESC)",
    ),
    (
        "ix_permission_history_target_type_start",
        "permission_history "
        "(target_table, target_id, permission_type, start_date DESC)",
    ),
    (
        "ix_measuring_point_history_thing_start",
        "measuring_point_history (thing_id, start_date DESC)",
    ),
    (
        "ix_monitoring_frequency_history_thing_start",
        "monitoring_frequency_history (thing_id, start_date DESC)",
    ),
    ("ix_deployment_thing_id", "deployment (thing_id)"),
    ("ix_thing_contact_association_thing_id", "thing_contact_association (thing_id)"),
    (
        "ix_thing_contact_association_contact_id",
        "thing_contact_association (contact_id)",
    ),
    ("ix_well_purpose_thing_id", "well_purpose (thing_id)"),
    ("ix_well_casing_material_thing_id", "well_casing_material (thing_id)"),
    ("ix_well_screen_thing_id", "well_screen (thing_id)"),
    ("ix_thing_id_link_thing_id", "thing_id_link (thing_id)"),
    ("ix_thing_thing_type", "thing (thing_type)"),
    (
        "ix_thing_aquifer_association_thing_id",
        "thing_aquifer_association (thing_id)",
    ),
    # No index on transducer_observation (deployment_id, ...): the existing
    # uq_transducer_observation_deployment_parameter_datetime leads with
    # deployment_id and already serves the per-deployment aggregate.
]


def _safe_relation_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Unsafe relation name: {name!r}")
    return name


def _check_required_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot create the water well field operations layer. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_stats_view() -> str:
    """The expensive half: aggregates over the observation-scale tables."""
    safe_name = _safe_relation_name(STATS_VIEW)
    return f"""
        CREATE MATERIALIZED VIEW {safe_name} AS
        WITH wells AS (
            SELECT t.id AS thing_id
            FROM thing AS t
            WHERE t.thing_type = 'water well'
        ),
        manual_obs AS (
            SELECT
                fe.thing_id,
                o.id AS observation_id,
                o.observation_datetime,
                (o.value - COALESCE(o.measuring_point_height, 0)) AS depth_to_water
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN wells AS w ON w.thing_id = fe.thing_id
            WHERE
                fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL
                AND o.observation_datetime IS NOT NULL
        ),
        manual_agg AS (
            SELECT
                m.thing_id,
                COUNT(*)::integer AS manual_water_level_count,
                (
                    MIN(m.observation_datetime) AT TIME ZONE 'UTC'
                )::date AS manual_water_level_first_date,
                (
                    MAX(m.observation_datetime) AT TIME ZONE 'UTC'
                )::date AS manual_water_level_last_date
            FROM manual_obs AS m
            GROUP BY m.thing_id
        ),
        manual_last AS (
            SELECT DISTINCT ON (m.thing_id)
                m.thing_id,
                m.depth_to_water AS last_depth_to_water_ft
            FROM manual_obs AS m
            ORDER BY m.thing_id, m.observation_datetime DESC, m.observation_id DESC
        ),
        chemistry_agg AS (
            SELECT
                fe.thing_id,
                COUNT(DISTINCT s.id)::integer AS chemistry_sample_count,
                (
                    MAX(s.sample_date) AT TIME ZONE 'UTC'
                )::date AS chemistry_sample_last_date
            FROM sample AS s
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN wells AS w ON w.thing_id = fe.thing_id
            WHERE fa.activity_type = 'water chemistry'
            GROUP BY fe.thing_id
        ),
        field_event_agg AS (
            SELECT
                fe.thing_id,
                COUNT(*)::integer AS field_event_count,
                (
                    MAX(fe.event_date) AT TIME ZONE 'UTC'
                )::date AS field_event_last_date
            FROM field_event AS fe
            JOIN wells AS w ON w.thing_id = fe.thing_id
            GROUP BY fe.thing_id
        ),
        continuous_agg AS (
            SELECT
                d.thing_id,
                COUNT(*)::bigint AS continuous_reading_count,
                MIN(tobs.observation_datetime) AS continuous_first_datetime,
                MAX(tobs.observation_datetime) AS continuous_last_datetime
            FROM transducer_observation AS tobs
            JOIN deployment AS d ON d.id = tobs.deployment_id
            JOIN wells AS w ON w.thing_id = d.thing_id
            GROUP BY d.thing_id
        )
        SELECT
            w.thing_id,
            COALESCE(ma.manual_water_level_count, 0) AS manual_water_level_count,
            ma.manual_water_level_first_date,
            ma.manual_water_level_last_date,
            ml.last_depth_to_water_ft,
            COALESCE(ca.chemistry_sample_count, 0) AS chemistry_sample_count,
            ca.chemistry_sample_last_date,
            COALESCE(fea.field_event_count, 0) AS field_event_count,
            fea.field_event_last_date,
            COALESCE(co.continuous_reading_count, 0) AS continuous_reading_count,
            co.continuous_first_datetime,
            co.continuous_last_datetime
        FROM wells AS w
        LEFT JOIN manual_agg AS ma ON ma.thing_id = w.thing_id
        LEFT JOIN manual_last AS ml ON ml.thing_id = w.thing_id
        LEFT JOIN chemistry_agg AS ca ON ca.thing_id = w.thing_id
        LEFT JOIN field_event_agg AS fea ON fea.thing_id = w.thing_id
        LEFT JOIN continuous_agg AS co ON co.thing_id = w.thing_id
    """


def _create_feature_view() -> str:
    """The live half: everything a stale answer would misreport."""
    safe_name = _safe_relation_name(FEATURE_VIEW)
    safe_stats = _safe_relation_name(STATS_VIEW)
    logger_types = ", ".join(LOGGER_SENSOR_TYPES)
    notes_columns_sql = ",\n            ".join(
        f"""(
                SELECT string_agg(n.content, ' | ' ORDER BY n.id DESC)
                FROM notes AS n
                WHERE
                    n.target_table = 'thing'
                    AND n.target_id = t.id
                    AND n.note_type = '{note_type}'
            ) AS {_safe_relation_name(column_name)}"""
        for note_type, column_name in NOTE_TYPES
    )
    return f"""
        CREATE VIEW {safe_name} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        current_status AS (
            SELECT DISTINCT ON (sh.target_id, sh.status_type)
                sh.target_id AS thing_id,
                sh.status_type,
                sh.status_value,
                sh.start_date,
                sh.reason
            FROM status_history AS sh
            WHERE
                sh.target_table = 'thing'
                AND sh.start_date <= CURRENT_DATE
                AND (sh.end_date IS NULL OR sh.end_date >= CURRENT_DATE)
            ORDER BY sh.target_id, sh.status_type, sh.start_date DESC, sh.id DESC
        ),
        current_permission AS (
            SELECT DISTINCT ON (ph.target_id, ph.permission_type)
                ph.target_id AS thing_id,
                ph.permission_type,
                ph.permission_allowed,
                ph.contact_id
            FROM permission_history AS ph
            WHERE
                ph.target_table = 'thing'
                AND ph.start_date <= CURRENT_DATE
                AND (ph.end_date IS NULL OR ph.end_date >= CURRENT_DATE)
            ORDER BY
                ph.target_id, ph.permission_type, ph.start_date DESC, ph.id DESC
        ),
        current_measuring_point AS (
            SELECT DISTINCT ON (mp.thing_id)
                mp.thing_id,
                mp.measuring_point_height,
                mp.measuring_point_description,
                mp.start_date
            FROM measuring_point_history AS mp
            WHERE
                mp.start_date <= CURRENT_DATE
                AND (mp.end_date IS NULL OR mp.end_date >= CURRENT_DATE)
            ORDER BY mp.thing_id, mp.start_date DESC, mp.id DESC
        ),
        current_monitoring_frequency AS (
            SELECT DISTINCT ON (mf.thing_id)
                mf.thing_id,
                mf.monitoring_frequency,
                mf.start_date
            FROM monitoring_frequency_history AS mf
            WHERE
                mf.start_date <= CURRENT_DATE
                AND (mf.end_date IS NULL OR mf.end_date >= CURRENT_DATE)
            ORDER BY mf.thing_id, mf.start_date DESC, mf.id DESC
        ),
        installed_deployments AS (
            -- Every currently-installed sensor, not just loggers -- a camera
            -- or barometer must not be invisible just because it cannot log
            -- on its own. See logger_count below for the narrower has_datalogger
            -- signal.
            SELECT
                d.id AS deployment_id,
                d.thing_id,
                d.installation_date,
                d.recording_interval,
                d.recording_interval_units,
                d.hanging_point_description,
                se.sensor_type,
                se.model,
                se.serial_no,
                se.sensor_status
            FROM deployment AS d
            JOIN sensor AS se ON se.id = d.sensor_id
            WHERE d.installation_date IS NOT NULL AND d.removal_date IS NULL
        ),
        installed_equipment AS (
            -- Aggregated, not DISTINCT ON: a well running more than one
            -- current sensor lists all of them. All eight columns are ordered
            -- by sensor_type, so position N in one list is the same
            -- deployment as position N in the others -- which is why every
            -- expression but sensor_type itself is wrapped in COALESCE(..,
            -- ''): sensor_type is NOT NULL on sensor, but a deployment can
            -- easily have a null model, recording_interval, etc. (a camera
            -- has no recording interval), and plain string_agg silently
            -- drops null inputs, shortening that one column's list and
            -- breaking the position-N-means-the-same-deployment guarantee.
            -- An empty segment between two ';' means "this sensor has no
            -- value for this field," not "this sensor doesn't exist."
            SELECT
                idpl.thing_id,
                string_agg(
                    idpl.sensor_type, '; ' ORDER BY idpl.sensor_type
                ) AS sensor_type,
                string_agg(
                    COALESCE(idpl.model, ''), '; ' ORDER BY idpl.sensor_type
                ) AS model,
                string_agg(
                    COALESCE(idpl.serial_no, ''), '; ' ORDER BY idpl.sensor_type
                ) AS serial_no,
                string_agg(
                    COALESCE(idpl.sensor_status, ''), '; ' ORDER BY idpl.sensor_type
                ) AS sensor_status,
                string_agg(
                    COALESCE(idpl.installation_date::text, ''),
                    '; ' ORDER BY idpl.sensor_type
                ) AS installed_date,
                string_agg(
                    COALESCE(idpl.recording_interval::text, ''),
                    '; ' ORDER BY idpl.sensor_type
                ) AS recording_interval,
                string_agg(
                    COALESCE(idpl.recording_interval_units, ''),
                    '; ' ORDER BY idpl.sensor_type
                ) AS recording_interval_units,
                string_agg(
                    COALESCE(idpl.hanging_point_description, ''),
                    '; ' ORDER BY idpl.sensor_type
                ) AS hanging_point_desc
            FROM installed_deployments AS idpl
            GROUP BY idpl.thing_id
        ),
        logger_count AS (
            SELECT
                idpl.thing_id,
                COUNT(*)::integer AS datalogger_deployment_count
            FROM installed_deployments AS idpl
            WHERE idpl.sensor_type IN ({logger_types})
            GROUP BY idpl.thing_id
        ),
        screens AS (
            -- Full per-interval detail, not a min/max summary: a well with
            -- more than one screen keeps them all rather than collapsing to
            -- an overall depth range. All three ordered by screen_depth_top
            -- (nulls last), and each wrapped in COALESCE(..., '') for the
            -- same reason as installed_equipment above -- screen_depth_top,
            -- screen_depth_bottom, and screen_description are all nullable
            -- independently of each other, and plain string_agg would drop
            -- a null and misalign the other two columns' positions.
            SELECT
                ws.thing_id,
                COUNT(*)::integer AS screen_count,
                string_agg(
                    COALESCE(ws.screen_depth_top::text, ''), '; '
                    ORDER BY ws.screen_depth_top NULLS LAST
                ) AS screen_depth_top,
                string_agg(
                    COALESCE(ws.screen_depth_bottom::text, ''), '; '
                    ORDER BY ws.screen_depth_top NULLS LAST
                ) AS screen_depth_bottom,
                string_agg(
                    COALESCE(ws.screen_description, ''), '; '
                    ORDER BY ws.screen_depth_top NULLS LAST
                ) AS screen_description
            FROM well_screen AS ws
            GROUP BY ws.thing_id
        ),
        thing_contacts AS (
            SELECT
                tca.thing_id,
                c.id AS contact_id,
                c.name,
                c.organization,
                c.role,
                c.contact_type
            FROM thing_contact_association AS tca
            JOIN contact AS c ON c.id = tca.contact_id
        ),
        contact_agg AS (
            SELECT
                tc.thing_id,
                COUNT(DISTINCT tc.contact_id)::integer AS contact_count,
                string_agg(
                    DISTINCT tc.name, ', ' ORDER BY tc.name
                ) AS contact_names
            FROM thing_contacts AS tc
            GROUP BY tc.thing_id
        ),
        primary_contact AS (
            -- Prefer a contact recorded as Primary, but fall back to any
            -- contact on the well rather than publishing a blank name next to
            -- a non-zero contact_count. primary_contact_type says which case
            -- this is, so the fallback is visible rather than implied.
            SELECT DISTINCT ON (tc.thing_id)
                tc.thing_id,
                tc.contact_id,
                tc.name,
                tc.organization,
                tc.role,
                tc.contact_type
            FROM thing_contacts AS tc
            ORDER BY
                tc.thing_id,
                (tc.contact_type = 'Primary') DESC NULLS LAST,
                tc.contact_id
        )
        SELECT
            t.id AS id,
            t.name,
            'water well'::text AS station_type,
            t.release_status,
            (
                SELECT string_agg(
                    DISTINCT
                        COALESCE(tl.alternate_organization, 'unknown')
                        || ': '
                        || tl.alternate_id,
                    ', '
                    ORDER BY
                        COALESCE(tl.alternate_organization, 'unknown')
                        || ': '
                        || tl.alternate_id
                )
                FROM thing_id_link AS tl
                WHERE tl.thing_id = t.id
            ) AS alternate_ids,
            -- Decimal degrees alongside the geometry. A crew types these into
            -- a handheld GPS or reads them over the radio; the geometry column
            -- is for the map, and a CSV export of this layer drops it.
            ST_Y(l.point) AS latitude,
            ST_X(l.point) AS longitude,
            l.elevation,

            -- Construction, same column names as the thing-type views.
            t.well_depth,
            t.hole_depth,
            t.well_casing_diameter,
            t.well_casing_depth,
            t.well_completion_date,
            t.well_driller_name,
            t.well_construction_method,
            t.well_pump_type,
            t.well_pump_depth,
            t.formation_completion_code,
            (
                SELECT lt.definition
                FROM lexicon_term AS lt
                WHERE lt.term = t.formation_completion_code
            ) AS formation_completion_description,
            (
                SELECT string_agg(DISTINCT wp.purpose, ', ' ORDER BY wp.purpose)
                FROM well_purpose AS wp
                WHERE wp.thing_id = t.id
            ) AS well_purpose,
            (
                SELECT string_agg(
                    DISTINCT wcm.material, ', ' ORDER BY wcm.material
                )
                FROM well_casing_material AS wcm
                WHERE wcm.thing_id = t.id
            ) AS well_casing_material,
            (
                SELECT string_agg(DISTINCT asys.name, ', ' ORDER BY asys.name)
                FROM thing_aquifer_association AS taa
                JOIN aquifer_system AS asys ON asys.id = taa.aquifer_system_id
                WHERE taa.thing_id = t.id
            ) AS aquifer_system_name,
            scr.screen_count,
            scr.screen_depth_top,
            scr.screen_depth_bottom,
            scr.screen_description,

            -- Measuring point, current record.
            cmp.measuring_point_height AS mp_height,
            cmp.measuring_point_description AS mp_description,

            -- Status, current record per status type.
            well_st.status_value AS well_status,
            mon_st.status_value AS monitoring_status,
            open_st.status_value AS open_status,
            dl_st.status_value AS datalogger_suitability_status,

            wl_perm.permission_allowed AS may_measure_water_level,
            chem_perm.permission_allowed AS may_sample_water_chemistry,
            dl_perm.permission_allowed AS may_install_datalogger,
            CASE WHEN wl_perm.permission_allowed IS TRUE THEN granter.name END AS permission_granted_by,

            -- Monitoring programme.
            cmf.monitoring_frequency,
            grp.group_names,
            grp.group_types,

            -- Manual water levels (from the stats matview).
            COALESCE(st.manual_water_level_count, 0) AS manual_water_level_count,
            st.manual_water_level_first_date,
            st.manual_water_level_last_date,
            (
                CURRENT_DATE - st.manual_water_level_last_date
            ) AS days_since_manual_water_level,
            st.last_depth_to_water_ft,

            -- Chemistry sampling (from the stats matview).
            COALESCE(st.chemistry_sample_count, 0) AS chemistry_sample_count,
            st.chemistry_sample_last_date,
            (
                CURRENT_DATE - st.chemistry_sample_last_date
            ) AS days_since_chemistry_sample,

            -- Field visits (from the stats matview).
            COALESCE(st.field_event_count, 0) AS field_event_count,
            st.field_event_last_date AS date_last_visited,

            -- Currently installed equipment, any sensor type -- see
            -- installed_equipment above. has_datalogger/
            -- datalogger_deployment_count stay logger-scoped.
            (lc.thing_id IS NOT NULL) AS has_datalogger,
            COALESCE(lc.datalogger_deployment_count, 0)
                AS datalogger_deployment_count,
            ie.sensor_type,
            ie.model,
            ie.serial_no,
            ie.sensor_status,
            ie.installed_date,
            ie.recording_interval,
            ie.recording_interval_units,
            ie.hanging_point_desc,
            COALESCE(st.continuous_reading_count, 0) AS continuous_reading_count,
            st.continuous_first_datetime,
            st.continuous_last_datetime,
            (
                CURRENT_DATE
                - (st.continuous_last_datetime AT TIME ZONE 'UTC')::date
            ) AS days_since_continuous_reading,

            -- Contacts.
            COALESCE(cag.contact_count, 0) AS contact_count,
            pc.name AS primary_contact_name,
            pc.organization AS primary_contact_organization,
            pc.role AS primary_contact_role,
            pc.contact_type AS primary_contact_type,
            (
                SELECT p.phone_number
                FROM phone AS p
                WHERE p.contact_id = pc.contact_id
                ORDER BY p.id
                LIMIT 1
            ) AS primary_contact_phone,
            (
                SELECT e.email
                FROM email AS e
                WHERE e.contact_id = pc.contact_id
                ORDER BY e.id
                LIMIT 1
            ) AS primary_contact_email,
            cag.contact_names,

            -- Notes, one column per note_type. Separator is ' | ' rather than
            -- ', ' because the content is free text and routinely contains
            -- commas.
            {notes_columns_sql},

            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        LEFT JOIN {safe_stats} AS st ON st.thing_id = t.id
        LEFT JOIN current_status AS well_st
            ON well_st.thing_id = t.id AND well_st.status_type = 'Well Status'
        LEFT JOIN current_status AS mon_st
            ON mon_st.thing_id = t.id
            AND mon_st.status_type = 'Monitoring Status'
        LEFT JOIN current_status AS open_st
            ON open_st.thing_id = t.id AND open_st.status_type = 'Open Status'
        LEFT JOIN current_status AS dl_st
            ON dl_st.thing_id = t.id
            AND dl_st.status_type = 'Datalogger Suitability Status'
        LEFT JOIN current_permission AS wl_perm
            ON wl_perm.thing_id = t.id
            AND wl_perm.permission_type = 'Water Level Sample'
        LEFT JOIN current_permission AS chem_perm
            ON chem_perm.thing_id = t.id
            AND chem_perm.permission_type = 'Water Chemistry Sample'
        LEFT JOIN current_permission AS dl_perm
            ON dl_perm.thing_id = t.id
            AND dl_perm.permission_type = 'Datalogger Installation'
        LEFT JOIN contact AS granter ON granter.id = wl_perm.contact_id
        LEFT JOIN current_measuring_point AS cmp ON cmp.thing_id = t.id
        LEFT JOIN current_monitoring_frequency AS cmf ON cmf.thing_id = t.id
        LEFT JOIN installed_equipment AS ie ON ie.thing_id = t.id
        LEFT JOIN logger_count AS lc ON lc.thing_id = t.id
        LEFT JOIN contact_agg AS cag ON cag.thing_id = t.id
        LEFT JOIN primary_contact AS pc ON pc.thing_id = t.id
        LEFT JOIN screens AS scr ON scr.thing_id = t.id
        LEFT JOIN LATERAL (
            -- group_thing_association has no unique constraint on
            -- (group_id, thing_id), so DISTINCT before aggregating. Both
            -- strings are ordered by the same group name so they stay
            -- index-aligned with each other.
            SELECT
                string_agg(dm.group_name, ', ' ORDER BY dm.group_name)
                    AS group_names,
                string_agg(dm.group_type, ', ' ORDER BY dm.group_name)
                    AS group_types
            FROM (
                SELECT DISTINCT
                    g.id AS group_id,
                    g.name AS group_name,
                    g.group_type
                FROM group_thing_association AS gta
                JOIN "group" AS g ON g.id = gta.group_id
                WHERE gta.thing_id = t.id
            ) AS dm
        ) AS grp ON TRUE
        WHERE t.thing_type = 'water well'
    """


def upgrade() -> None:
    _check_required_tables()

    safe_stats = _safe_relation_name(STATS_VIEW)
    safe_feature = _safe_relation_name(FEATURE_VIEW)

    # The feature view depends on the stats matview, so it is dropped first and
    # created last.
    op.execute(text(f"DROP VIEW IF EXISTS {safe_feature}"))
    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {safe_stats}"))

    op.execute(text(_create_stats_view()))
    # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
    op.execute(
        text(
            f"CREATE UNIQUE INDEX ix_{safe_stats}_thing_id "
            f"ON {safe_stats} (thing_id)"
        )
    )
    op.execute(text(_create_feature_view()))

    for index_name, definition in SUPPORTING_INDEXES:
        op.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS {_safe_relation_name(index_name)} ON {definition}"
            )
        )


def downgrade() -> None:
    safe_stats = _safe_relation_name(STATS_VIEW)
    safe_feature = _safe_relation_name(FEATURE_VIEW)

    op.execute(text(f"DROP VIEW IF EXISTS {safe_feature}"))
    op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {safe_stats}"))

    for index_name, _definition in SUPPORTING_INDEXES:
        op.execute(text(f"DROP INDEX IF EXISTS {_safe_relation_name(index_name)}"))
