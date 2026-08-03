"""create internal ogc views

Companion migration to f4a5b6c7d8e9 (public release_status filter on ogc_*
views): creates a second, unfiltered copy of the same 22 relations, named
ogc_internal_<id>, backing the authenticated /ogcapi-internal mount
(core/pygeoapi.py::mount_pygeoapi_internal). Full parity with the public
set, per ticket A11 -- not a subset.

Also mirrors ogc_waterlevels/ogc_water_chemistry from z9a0b1c2d3e4 (added to
staging after this migration's original 22-relation scope was written, per
ADR3's EDR feature) as ogc_internal_waterlevels/ogc_internal_water_chemistry,
bringing the total to 24. Unfiltered in all three places the public views
predicate on release_status: the manual-readings and chemistry selects'
`o.release_status = 'public'`, and the transducer union's
`tobs.release_status = 'public'`.

The major/minor chemistry analyte-mapping CASE blocks and
STATIC_ANALYTE_COLUMNS lists below are intentionally character-for-character
identical (modulo view name) to their counterparts in f4a5b6c7d8e9 -- this
codebase keeps migrations self-contained with no cross-migration imports, so
the logic is duplicated here rather than shared. tests/test_migration_view_
parity.py enforces the two stay in sync: if you fix an analyte mapping in
one file, apply the same fix to the other.

ogc_internal_locations has no release_status predicate at all (unlike
ogc_locations, which is always public-only) -- the internal mount is
unfiltered by design, and ogc_internal_locations never existed before this
migration in any form.

ogc_internal_actively_monitored_wells gets no predicate of its own -- like
its public counterpart, it inherits whichever rows ogc_internal_water_well_
summary exposes (here, all of them) transitively via a direct JOIN. Because
of that JOIN, it must be dropped before ogc_internal_water_well_summary and
recreated after (same ordering constraint as the public side).

All 24 relations here are newly created by this migration -- none of them
existed in any form beforehand -- so downgrade() simply drops them rather
than recreating a prior state.

Revision ID: 2d3c3a268652
Revises: f4a5b6c7d8e9
Create Date: 2026-07-16 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "2d3c3a268652"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUIRED_TABLES = {
    "thing",
    "location",
    "location_thing_association",
    "group",
    "group_thing_association",
    "status_history",
    "observation",
    "sample",
    "field_activity",
    "field_event",
    "data_provenance",
    "NMA_MajorChemistry",
    "NMA_Chemistry_SampleInfo",
    "NMA_MinorTraceChemistry",
    # For the ogc_internal_waterlevels/ogc_internal_water_chemistry EDR
    # mirrors (see z9a0b1c2d3e4_add_edr_water_views.py).
    "transducer_observation",
    "deployment",
    "parameter",
}

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()

# Same 11 thing-type views as f4a5b6c7d8e9's THING_VIEWS.
THING_VIEWS = [
    ("water_wells", "water well"),
    ("springs", "spring"),
    ("diversions_surface_water", "diversion of surface water, etc."),
    ("ephemeral_streams", "ephemeral stream"),
    ("lakes_ponds_reservoirs", "lake, pond or reservoir"),
    ("meteorological_stations", "meteorological station"),
    ("other_things", "other"),
    ("outfalls_wastewater_return_flow", "outfall of wastewater or return flow"),
    ("perennial_streams", "perennial stream"),
    ("rock_sample_locations", "rock sample location"),
    ("soil_gas_sample_locations", "soil gas sample location"),
]


def _safe_view_id(view_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", view_id):
        raise ValueError(f"Unsafe view id: {view_id!r}")
    return view_id


def _drop_view_or_materialized_view(view_name: str) -> None:
    # DROP VIEW IF EXISTS / DROP MATERIALIZED VIEW IF EXISTS only suppress
    # "relation does not exist" -- Postgres still raises WrongObjectType if
    # the relation exists as the other kind (e.g. DROP VIEW against an
    # existing materialized view), so the relation's actual kind must be
    # checked first rather than trying both blindly.
    bind = op.get_bind()
    relkind = bind.execute(
        text("SELECT relkind FROM pg_class WHERE oid = to_regclass(:name)"),
        {"name": view_name},
    ).scalar()
    if relkind == "m":
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}"))
    elif relkind == "v":
        op.execute(text(f"DROP VIEW IF EXISTS {view_name}"))


def _check_required_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    missing = REQUIRED_TABLES - existing_tables
    if missing:
        raise RuntimeError(
            "Cannot create internal OGC views. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_thing_view(view_id: str, thing_type: str, public_only: bool) -> str:
    safe_view_id = _safe_view_id(view_id)
    escaped_thing_type = thing_type.replace("'", "''")
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW ogc_internal_{safe_view_id} AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        )
        SELECT
            t.id,
            t.name,
            t.first_visit_date,
            t.nma_pk_welldata,
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
            t.nma_formation_zone,
            t.release_status,
            l.elevation,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE t.thing_type = '{escaped_thing_type}'{release_filter}
    """


def _create_latest_depth_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_latest_depth_to_water_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        ranked_obs AS (
            SELECT
                fe.thing_id,
                o.id AS observation_id,
                o.observation_datetime,
                o.value,
                o.measuring_point_height,
                -- Treat NULL measuring_point_height as 0 when computing
                -- depth_to_water_bgs.
                (
                    o.value - COALESCE(o.measuring_point_height, 0)
                ) AS depth_to_water_bgs,
                ROW_NUMBER() OVER (
                    PARTITION BY fe.thing_id
                    ORDER BY o.observation_datetime DESC, o.id DESC
                ) AS rn
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN thing AS t ON t.id = fe.thing_id
            WHERE
                t.thing_type = 'water well'
                AND fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL{release_filter}
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            ro.observation_id,
            ro.observation_datetime,
            ro.value AS depth_to_water_reference,
            ro.measuring_point_height,
            ro.depth_to_water_bgs,
            l.point
        FROM ranked_obs AS ro
        JOIN thing AS t ON t.id = ro.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE ro.rn = 1
    """


def _create_avg_tds_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_avg_tds_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        tds_obs AS (
            SELECT
                csi.thing_id,
                mc.id AS major_chemistry_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate")::date AS observation_date,
                mc."SampleValue" AS sample_value,
                mc."Units" AS units
            FROM "NMA_MajorChemistry" AS mc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                t.thing_type = 'water well'
                AND mc."SampleValue" IS NOT NULL
                AND (
                    lower(coalesce(mc."Analyte", '')) IN (
                        'tds',
                        'total dissolved solids'
                    )
                    OR lower(coalesce(mc."Symbol", '')) = 'tds'
                ){release_filter}
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            COUNT(to2.major_chemistry_id)::integer AS tds_observation_count,
            AVG(to2.sample_value)::double precision AS avg_tds_value,
            MIN(to2.observation_date) AS first_tds_observation_date,
            MAX(to2.observation_date) AS last_tds_observation_date,
            l.point
        FROM tds_obs AS to2
        JOIN thing AS t ON t.id = to2.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        GROUP BY t.id, t.name, t.thing_type, l.point
    """


def _create_latest_tds_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW ogc_internal_latest_tds_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        tds_obs AS (
            SELECT
                csi.thing_id,
                mc.id AS major_chemistry_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate") AS observation_datetime,
                mc."SampleValue" AS sample_value,
                mc."Units" AS units
            FROM "NMA_MajorChemistry" AS mc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                t.thing_type = 'water well'
                AND mc."SampleValue" IS NOT NULL
                AND (
                    lower(coalesce(mc."Analyte", '')) IN (
                        'tds',
                        'total dissolved solids'
                    )
                    OR lower(coalesce(mc."Symbol", '')) = 'tds'
                ){release_filter}
        ),
        ranked_tds AS (
            SELECT
                to2.thing_id,
                to2.major_chemistry_id,
                to2.observation_datetime,
                to2.sample_value,
                to2.units,
                ROW_NUMBER() OVER (
                    PARTITION BY to2.thing_id
                    ORDER BY to2.observation_datetime DESC NULLS LAST, to2.major_chemistry_id DESC
                ) AS rn
            FROM tds_obs AS to2
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            rt.major_chemistry_id,
            rt.observation_datetime::date AS latest_tds_observation_date,
            rt.sample_value AS latest_tds_value,
            rt.units AS latest_tds_units,
            l.point
        FROM ranked_tds AS rt
        JOIN thing AS t ON t.id = rt.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE rt.rn = 1
    """


def _create_depth_to_water_trend_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_depth_to_water_trend_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        obs AS (
            SELECT
                fe.thing_id,
                o.observation_datetime,
                (o.value - COALESCE(o.measuring_point_height, 0)) AS depth_to_water_bgs
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN thing AS t ON t.id = fe.thing_id
            WHERE
                t.thing_type = 'water well'
                AND fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL
                AND o.observation_datetime IS NOT NULL{release_filter}
        ),
        agg AS (
            SELECT
                ob.thing_id,
                COUNT(*)::integer AS record_count,
                MIN(ob.observation_datetime) AS first_observation_datetime,
                MAX(ob.observation_datetime) AS last_observation_datetime,
                EXTRACT(EPOCH FROM (MAX(ob.observation_datetime) - MIN(ob.observation_datetime)))
                    / 31557600.0 AS span_years,
                REGR_SLOPE(
                    ob.depth_to_water_bgs,
                    EXTRACT(EPOCH FROM ob.observation_datetime)
                ) * 31557600.0 AS slope_ft_per_year
            FROM obs AS ob
            GROUP BY ob.thing_id
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            a.record_count,
            a.first_observation_datetime,
            a.last_observation_datetime,
            a.span_years,
            a.slope_ft_per_year,
            CASE
                WHEN a.record_count >= 10 OR (a.record_count >= 4 AND a.span_years >= 2.0) THEN
                    CASE
                        WHEN a.slope_ft_per_year IS NULL THEN 'not enough data'
                        WHEN a.slope_ft_per_year > 0.25 THEN 'increasing'
                        WHEN a.slope_ft_per_year < -0.25 THEN 'decreasing'
                        ELSE 'stable'
                    END
                ELSE 'not enough data'
            END AS trend_category,
            l.point
        FROM agg AS a
        JOIN thing AS t ON t.id = a.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
    """


def _create_water_well_summary_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_water_well_summary AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        wl_obs AS (
            SELECT
                fe.thing_id,
                o.id AS observation_id,
                o.observation_datetime,
                (o.value - COALESCE(o.measuring_point_height, 0)) AS water_level
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN thing AS t ON t.id = fe.thing_id
            WHERE
                t.thing_type = 'water well'
                AND fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL
                AND o.observation_datetime IS NOT NULL{release_filter}
        ),
        wl_agg AS (
            SELECT
                w.thing_id,
                COUNT(*)::integer AS total_water_levels,
                MIN(w.water_level) AS min_water_level,
                MAX(w.water_level) AS max_water_level,
                REGR_SLOPE(
                    w.water_level,
                    EXTRACT(EPOCH FROM w.observation_datetime)
                ) * 31557600.0 AS water_level_trend_ft_per_year
            FROM wl_obs AS w
            GROUP BY w.thing_id
        ),
        wl_last AS (
            SELECT
                ranked.thing_id,
                ranked.water_level AS last_water_level,
                ranked.observation_datetime AS last_water_level_datetime
            FROM (
                SELECT
                    w.thing_id,
                    w.water_level,
                    w.observation_datetime,
                    ROW_NUMBER() OVER (
                        PARTITION BY w.thing_id
                        ORDER BY w.observation_datetime DESC, w.observation_id DESC
                    ) AS rn
                FROM wl_obs AS w
            ) AS ranked
            WHERE ranked.rn = 1
        )
        SELECT
            t.id AS id,
            t.name,
            t.well_depth,
            l.elevation,
            dpl.collection_method AS elevation_method,
            t.nma_formation_zone AS formation_zone,
            wa.total_water_levels,
            wl.last_water_level,
            wl.last_water_level_datetime,
            wa.min_water_level,
            wa.max_water_level,
            wa.water_level_trend_ft_per_year,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        JOIN wl_agg AS wa ON wa.thing_id = t.id
        LEFT JOIN wl_last AS wl ON wl.thing_id = t.id
        LEFT JOIN LATERAL (
            SELECT dp.collection_method
            FROM data_provenance AS dp
            WHERE
                dp.target_table = 'location'
                AND dp.target_id = l.id
                AND dp.field_name = 'elevation'
            ORDER BY dp.id DESC
            LIMIT 1
        ) AS dpl ON true
        WHERE t.thing_type = 'water well'
          AND wa.total_water_levels > 0
    """


# Static analyte columns for major chemistry pivots.
# Includes aliases observed in current DB values (e.g., Ca(total), IONBAL, TAn, TCat, Na+K).
# Kept character-for-character identical to f4a5b6c7d8e9's copy -- see
# tests/test_migration_view_parity.py.
STATIC_ANALYTE_COLUMNS_MAJOR: list[tuple[str, str]] = [
    ("tds", "tds"),
    ("calcium", "calcium"),
    ("calcium_total", "calcium_total"),
    ("magnesium", "magnesium"),
    ("magnesium_total", "magnesium_total"),
    ("sodium", "sodium"),
    ("sodium_total", "sodium_total"),
    ("potassium", "potassium"),
    ("potassium_total", "potassium_total"),
    ("sodium_plus_potassium", "sodium_plus_potassium"),
    ("bicarbonate", "bicarbonate"),
    ("carbonate", "carbonate"),
    ("sulfate", "sulfate"),
    ("chloride", "chloride"),
    ("ion_balance", "ion_balance"),
    ("total_anions", "total_anions"),
    ("total_cations", "total_cations"),
    ("alkalinity", "alkalinity"),
    ("hardness", "hardness"),
    ("specific_conductance", "specific_conductance"),
    ("ph", "ph"),
    ("nitrate", "nitrate"),
    ("fluoride", "fluoride"),
    ("silica", "silica"),
]


def _major_chemistry_select_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.sample_value) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS_MAJOR
        ]
    )


def _major_chemistry_unit_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.units) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}_units"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS_MAJOR
        ]
    )


def _create_major_chemistry_results_view(public_only: bool) -> str:
    static_columns = _major_chemistry_select_columns()
    static_unit_columns = _major_chemistry_unit_columns()
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_major_chemistry_results AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        chemistry_rows AS (
            SELECT
                csi.thing_id,
                mc.id AS result_id,
                COALESCE(mc."AnalysisDate", csi."CollectionDate") AS observation_datetime,
                trim(mc."Analyte") AS analyte_name,
                trim(mc."Symbol") AS symbol_name,
                mc."SampleValue"::double precision AS sample_value,
                mc."Units" AS units
            FROM "NMA_MajorChemistry" AS mc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mc.chemistry_sample_info_id
            JOIN thing AS t
                ON t.id = csi.thing_id
            WHERE mc."SampleValue" IS NOT NULL
              AND t.thing_type = 'water well'{release_filter}
        ),
        normalized_rows AS (
            SELECT
                cr.thing_id,
                cr.result_id,
                cr.observation_datetime,
                NULLIF(
                    regexp_replace(
                        lower(trim(coalesce(cr.analyte_name, ''))),
                        '[^a-z0-9]+',
                        '',
                        'g'
                    ),
                    ''
                ) AS analyte_token,
                NULLIF(
                    regexp_replace(
                        lower(trim(coalesce(cr.symbol_name, ''))),
                        '[^a-z0-9]+',
                        '',
                        'g'
                    ),
                    ''
                ) AS symbol_token,
                cr.sample_value,
                cr.units
            FROM chemistry_rows AS cr
        ),
        mapped_rows AS (
            SELECT
                nr.thing_id,
                nr.result_id,
                nr.observation_datetime,
                CASE
                    WHEN coalesce(nr.symbol_token, '') = 'tds'
                        OR coalesce(nr.analyte_token, '') IN ('tds', 'totaldissolvedsolids')
                        THEN 'tds'

                    WHEN coalesce(nr.symbol_token, '') = 'ca'
                        OR coalesce(nr.analyte_token, '') = 'ca'
                        THEN 'calcium'
                    WHEN coalesce(nr.analyte_token, '') = 'catotal'
                        THEN 'calcium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'mg'
                        OR coalesce(nr.analyte_token, '') = 'mg'
                        THEN 'magnesium'
                    WHEN coalesce(nr.analyte_token, '') = 'mgtotal'
                        THEN 'magnesium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'na'
                        OR coalesce(nr.analyte_token, '') = 'na'
                        THEN 'sodium'
                    WHEN coalesce(nr.analyte_token, '') = 'natotal'
                        THEN 'sodium_total'

                    WHEN coalesce(nr.symbol_token, '') = 'k'
                        OR coalesce(nr.analyte_token, '') = 'k'
                        THEN 'potassium'
                    WHEN coalesce(nr.analyte_token, '') = 'ktotal'
                        THEN 'potassium_total'

                    WHEN coalesce(nr.analyte_token, '') = 'nak'
                        THEN 'sodium_plus_potassium'

                    WHEN coalesce(nr.symbol_token, '') = 'hco3'
                        OR coalesce(nr.analyte_token, '') = 'hco3'
                        THEN 'bicarbonate'
                    WHEN coalesce(nr.symbol_token, '') = 'co3'
                        OR coalesce(nr.analyte_token, '') = 'co3'
                        THEN 'carbonate'
                    WHEN coalesce(nr.symbol_token, '') = 'so4'
                        OR coalesce(nr.analyte_token, '') = 'so4'
                        THEN 'sulfate'
                    WHEN coalesce(nr.symbol_token, '') = 'cl'
                        OR coalesce(nr.analyte_token, '') = 'cl'
                        THEN 'chloride'

                    WHEN coalesce(nr.analyte_token, '') = 'ionbal'
                        THEN 'ion_balance'
                    WHEN coalesce(nr.analyte_token, '') = 'tan'
                        THEN 'total_anions'
                    WHEN coalesce(nr.analyte_token, '') = 'tcat'
                        THEN 'total_cations'

                    WHEN coalesce(nr.analyte_token, '') IN ('alk', 'alkalinity')
                        THEN 'alkalinity'
                    WHEN coalesce(nr.analyte_token, '') IN ('hrd', 'hardness')
                        THEN 'hardness'
                    WHEN coalesce(nr.analyte_token, '') IN (
                        'condlab',
                        'specificconductance',
                        'specificconductivity',
                        'conductivity'
                    )
                        THEN 'specific_conductance'
                    WHEN coalesce(nr.symbol_token, '') = 'ph'
                        OR coalesce(nr.analyte_token, '') IN ('ph', 'phl')
                        THEN 'ph'

                    WHEN coalesce(nr.symbol_token, '') = 'no3'
                        OR coalesce(nr.analyte_token, '') IN ('no3', 'nitrate')
                        THEN 'nitrate'
                    WHEN coalesce(nr.symbol_token, '') = 'f'
                        OR coalesce(nr.analyte_token, '') IN ('f', 'fluoride')
                        THEN 'fluoride'
                    WHEN coalesce(nr.symbol_token, '') = 'sio2'
                        OR coalesce(nr.analyte_token, '') IN ('sio2', 'silica')
                        THEN 'silica'

                    ELSE NULL
                END AS analyte_key,
                nr.sample_value,
                nr.units
            FROM normalized_rows AS nr
        ),
        latest_results AS (
            SELECT
                mr.thing_id,
                mr.analyte_key,
                mr.sample_value,
                mr.units,
                mr.observation_datetime,
                ROW_NUMBER() OVER (
                    PARTITION BY mr.thing_id, mr.analyte_key
                    ORDER BY mr.observation_datetime DESC NULLS LAST, mr.result_id DESC
                ) AS rn
            FROM mapped_rows AS mr
            WHERE mr.analyte_key IS NOT NULL
        )
        SELECT
            t.id AS id,
            ll.location_id,
            t.name,
            t.thing_type,
            COUNT(*)::integer AS analyte_count,
            MAX(lr.observation_datetime::date) AS latest_chemistry_date,
{static_columns},
{static_unit_columns},
            l.point
        FROM latest_results AS lr
        JOIN thing AS t ON t.id = lr.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE lr.rn = 1
        GROUP BY t.id, ll.location_id, t.name, t.thing_type, l.point
    """


# Kept character-for-character identical to f4a5b6c7d8e9's copy -- see
# tests/test_migration_view_parity.py.
STATIC_ANALYTE_COLUMNS_MINOR: list[tuple[str, str]] = [
    ("h2r", "h2r"),
    ("o18r", "o18r"),
    ("c13r", "c13r"),
    ("c14", "c14"),
    ("c14_years", "c14_years"),
    ("fluoride", "fluoride"),
    ("barium", "barium"),
    ("barium_total", "barium_total"),
    ("copper", "copper"),
    ("copper_total", "copper_total"),
    ("zinc", "zinc"),
    ("zinc_total", "zinc_total"),
    ("molybdenum", "molybdenum"),
    ("molybdenum_total", "molybdenum_total"),
    ("silica", "silica"),
    ("silicon", "silicon"),
    ("silicon_total", "silicon_total"),
    ("manganese", "manganese"),
    ("manganese_total", "manganese_total"),
    ("iron", "iron"),
    ("iron_total", "iron_total"),
    ("strontium", "strontium"),
    ("strontium_total", "strontium_total"),
    ("chromium", "chromium"),
    ("chromium_total", "chromium_total"),
    ("boron", "boron"),
    ("boron_total", "boron_total"),
    ("uranium", "uranium"),
    ("uranium_total", "uranium_total"),
    ("lithium", "lithium"),
    ("lithium_total", "lithium_total"),
    ("silver", "silver"),
    ("silver_total", "silver_total"),
    ("antimony", "antimony"),
    ("antimony_total", "antimony_total"),
    ("beryllium", "beryllium"),
    ("beryllium_total", "beryllium_total"),
    ("lead", "lead"),
    ("lead_total", "lead_total"),
    ("thallium", "thallium"),
    ("thallium_total", "thallium_total"),
    ("bromide", "bromide"),
    ("selenium", "selenium"),
    ("selenium_total", "selenium_total"),
    ("vanadium", "vanadium"),
    ("vanadium_total", "vanadium_total"),
    ("aluminum", "aluminum"),
    ("aluminum_total", "aluminum_total"),
    ("arsenic", "arsenic"),
    ("arsenic_total", "arsenic_total"),
    ("nickel", "nickel"),
    ("nickel_total", "nickel_total"),
    ("cadmium", "cadmium"),
    ("cadmium_total", "cadmium_total"),
    ("cobalt", "cobalt"),
    ("cobalt_total", "cobalt_total"),
    ("phosphate", "phosphate"),
    ("nitrite", "nitrite"),
    ("nitrate", "nitrate"),
    ("nitrate_as_n", "nitrate_as_n"),
    ("thorium", "thorium"),
    ("thorium_total", "thorium_total"),
    ("tin", "tin"),
    ("tin_total", "tin_total"),
    ("mercury", "mercury"),
    ("mercury_total", "mercury_total"),
    ("titanium", "titanium"),
    ("titanium_total", "titanium_total"),
]


def _minor_chemistry_value_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.sample_value) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS_MINOR
        ]
    )


def _minor_chemistry_unit_columns() -> str:
    return ",\n".join(
        [
            (
                "            MAX(lr.units) FILTER "
                f"(WHERE lr.analyte_key = '{analyte_key}') AS {column_name}_units"
            )
            for analyte_key, column_name in STATIC_ANALYTE_COLUMNS_MINOR
        ]
    )


def _create_minor_chemistry_wells_view(public_only: bool) -> str:
    value_columns = _minor_chemistry_value_columns()
    unit_columns = _minor_chemistry_unit_columns()
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_minor_chemistry_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        chemistry_rows AS (
            SELECT
                csi.thing_id,
                mtc.id AS result_id,
                COALESCE(mtc.analysis_date::timestamp, csi."CollectionDate") AS observation_datetime,
                trim(mtc.analyte) AS analyte_name,
                mtc.sample_value::double precision AS sample_value,
                mtc.units AS units
            FROM "NMA_MinorTraceChemistry" AS mtc
            JOIN "NMA_Chemistry_SampleInfo" AS csi
                ON csi.id = mtc.chemistry_sample_info_id
            JOIN thing AS t ON t.id = csi.thing_id
            WHERE
                mtc.sample_value IS NOT NULL
                AND t.thing_type = 'water well'{release_filter}
        ),
        normalized_rows AS (
            SELECT
                cr.thing_id,
                cr.result_id,
                cr.observation_datetime,
                NULLIF(
                    regexp_replace(
                        lower(trim(coalesce(cr.analyte_name, ''))),
                        '[^a-z0-9]+',
                        '',
                        'g'
                    ),
                    ''
                ) AS analyte_token,
                cr.sample_value,
                cr.units
            FROM chemistry_rows AS cr
        ),
        mapped_rows AS (
            SELECT
                nr.thing_id,
                nr.result_id,
                nr.observation_datetime,
                CASE
                    WHEN coalesce(nr.analyte_token, '') = 'h2r' THEN 'h2r'
                    WHEN coalesce(nr.analyte_token, '') = 'o18r' THEN 'o18r'
                    WHEN coalesce(nr.analyte_token, '') = 'c13r' THEN 'c13r'
                    WHEN coalesce(nr.analyte_token, '') = 'c14' THEN 'c14'
                    WHEN coalesce(nr.analyte_token, '') = 'c14years' THEN 'c14_years'

                    WHEN coalesce(nr.analyte_token, '') = 'f' THEN 'fluoride'
                    WHEN coalesce(nr.analyte_token, '') = 'ba' THEN 'barium'
                    WHEN coalesce(nr.analyte_token, '') = 'batotal' THEN 'barium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cu' THEN 'copper'
                    WHEN coalesce(nr.analyte_token, '') = 'cutotal' THEN 'copper_total'
                    WHEN coalesce(nr.analyte_token, '') = 'zn' THEN 'zinc'
                    WHEN coalesce(nr.analyte_token, '') = 'zntotal' THEN 'zinc_total'
                    WHEN coalesce(nr.analyte_token, '') = 'mo' THEN 'molybdenum'
                    WHEN coalesce(nr.analyte_token, '') = 'mototal' THEN 'molybdenum_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sio2' THEN 'silica'
                    WHEN coalesce(nr.analyte_token, '') = 'si' THEN 'silicon'
                    WHEN coalesce(nr.analyte_token, '') = 'sitotal' THEN 'silicon_total'
                    WHEN coalesce(nr.analyte_token, '') = 'mn' THEN 'manganese'
                    WHEN coalesce(nr.analyte_token, '') = 'mntotal' THEN 'manganese_total'
                    WHEN coalesce(nr.analyte_token, '') = 'fe' THEN 'iron'
                    WHEN coalesce(nr.analyte_token, '') = 'fetotal' THEN 'iron_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sr' THEN 'strontium'
                    WHEN coalesce(nr.analyte_token, '') = 'srtotal' THEN 'strontium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cr' THEN 'chromium'
                    WHEN coalesce(nr.analyte_token, '') = 'crtotal' THEN 'chromium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'b' THEN 'boron'
                    WHEN coalesce(nr.analyte_token, '') = 'btotal' THEN 'boron_total'
                    WHEN coalesce(nr.analyte_token, '') = 'u' THEN 'uranium'
                    WHEN coalesce(nr.analyte_token, '') = 'utotal' THEN 'uranium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'li' THEN 'lithium'
                    WHEN coalesce(nr.analyte_token, '') = 'litotal' THEN 'lithium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ag' THEN 'silver'
                    WHEN coalesce(nr.analyte_token, '') = 'agtotal' THEN 'silver_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sb' THEN 'antimony'
                    WHEN coalesce(nr.analyte_token, '') = 'sbtotal' THEN 'antimony_total'
                    WHEN coalesce(nr.analyte_token, '') = 'be' THEN 'beryllium'
                    WHEN coalesce(nr.analyte_token, '') = 'betotal' THEN 'beryllium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'pb' THEN 'lead'
                    WHEN coalesce(nr.analyte_token, '') = 'pbtotal' THEN 'lead_total'
                    WHEN coalesce(nr.analyte_token, '') = 'tl' THEN 'thallium'
                    WHEN coalesce(nr.analyte_token, '') = 'tltotal' THEN 'thallium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'br' THEN 'bromide'
                    WHEN coalesce(nr.analyte_token, '') = 'se' THEN 'selenium'
                    WHEN coalesce(nr.analyte_token, '') = 'setotal' THEN 'selenium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'v' THEN 'vanadium'
                    WHEN coalesce(nr.analyte_token, '') = 'vtotal' THEN 'vanadium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'al' THEN 'aluminum'
                    WHEN coalesce(nr.analyte_token, '') = 'altotal' THEN 'aluminum_total'
                    WHEN coalesce(nr.analyte_token, '') = 'as' THEN 'arsenic'
                    WHEN coalesce(nr.analyte_token, '') = 'astotal' THEN 'arsenic_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ni' THEN 'nickel'
                    WHEN coalesce(nr.analyte_token, '') = 'nitotal' THEN 'nickel_total'
                    WHEN coalesce(nr.analyte_token, '') = 'cd' THEN 'cadmium'
                    WHEN coalesce(nr.analyte_token, '') = 'cdtotal' THEN 'cadmium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'co' THEN 'cobalt'
                    WHEN coalesce(nr.analyte_token, '') = 'cototal' THEN 'cobalt_total'
                    WHEN coalesce(nr.analyte_token, '') = 'po4' THEN 'phosphate'
                    WHEN coalesce(nr.analyte_token, '') = 'no2' THEN 'nitrite'
                    WHEN coalesce(nr.analyte_token, '') = 'no3' THEN 'nitrate'
                    WHEN coalesce(nr.analyte_token, '') = 'no3n' THEN 'nitrate_as_n'
                    WHEN coalesce(nr.analyte_token, '') = 'th' THEN 'thorium'
                    WHEN coalesce(nr.analyte_token, '') = 'thtotal' THEN 'thorium_total'
                    WHEN coalesce(nr.analyte_token, '') = 'sn' THEN 'tin'
                    WHEN coalesce(nr.analyte_token, '') = 'sntotal' THEN 'tin_total'
                    WHEN coalesce(nr.analyte_token, '') = 'hg' THEN 'mercury'
                    WHEN coalesce(nr.analyte_token, '') = 'hgtotal' THEN 'mercury_total'
                    WHEN coalesce(nr.analyte_token, '') = 'ti' THEN 'titanium'
                    WHEN coalesce(nr.analyte_token, '') = 'titotal' THEN 'titanium_total'
                    ELSE NULL
                END AS analyte_key,
                nr.sample_value,
                nr.units
            FROM normalized_rows AS nr
        ),
        latest_results AS (
            SELECT
                mr.thing_id,
                mr.analyte_key,
                mr.sample_value,
                mr.units,
                mr.observation_datetime,
                ROW_NUMBER() OVER (
                    PARTITION BY mr.thing_id, mr.analyte_key
                    ORDER BY mr.observation_datetime DESC NULLS LAST, mr.result_id DESC
                ) AS rn
            FROM mapped_rows AS mr
            WHERE mr.analyte_key IS NOT NULL
        )
        SELECT
            t.id AS id,
            ll.location_id,
            t.name,
            t.thing_type,
            COUNT(*)::integer AS analyte_count,
            MAX(lr.observation_datetime::date) AS latest_chemistry_date,
{value_columns},
{unit_columns},
            l.point
        FROM latest_results AS lr
        JOIN thing AS t ON t.id = lr.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE lr.rn = 1
          AND t.thing_type = 'water well'
        GROUP BY t.id, ll.location_id, t.name, t.thing_type, l.point
    """


METERS_TO_FEET = 3.28084


def _create_water_elevation_view(public_only: bool) -> str:
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    return f"""
        CREATE MATERIALIZED VIEW ogc_internal_water_elevation_wells AS
        WITH latest_location AS (
{LATEST_LOCATION_CTE}
        ),
        ranked_obs AS (
            SELECT
                fe.thing_id,
                o.id AS observation_id,
                o.observation_datetime,
                CASE
                    WHEN lower(trim(o.unit)) IN ('m', 'meter', 'meters', 'metre', 'metres') THEN
                        (o.value * {METERS_TO_FEET}) - COALESCE(o.measuring_point_height, 0)
                    WHEN lower(trim(o.unit)) IN ('ft', 'foot', 'feet') THEN
                        o.value - COALESCE(o.measuring_point_height, 0)
                    ELSE
                        NULL
                END AS depth_to_water_below_ground_surface
            FROM observation AS o
            JOIN sample AS s ON s.id = o.sample_id
            JOIN field_activity AS fa ON fa.id = s.field_activity_id
            JOIN field_event AS fe ON fe.id = fa.field_event_id
            JOIN thing AS t ON t.id = fe.thing_id
            WHERE
                t.thing_type = 'water well'
                AND fa.activity_type = 'groundwater level'
                AND o.value IS NOT NULL
                AND o.observation_datetime IS NOT NULL
                AND lower(trim(o.unit)) IN (
                    'm',
                    'meter',
                    'meters',
                    'metre',
                    'metres',
                    'ft',
                    'foot',
                    'feet'
                ){release_filter}
        ),
        latest_obs AS (
            SELECT
                ro.*,
                ROW_NUMBER() OVER (
                    PARTITION BY ro.thing_id
                    ORDER BY ro.observation_datetime DESC, ro.observation_id DESC
                ) AS rn
            FROM ranked_obs AS ro
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            lo.observation_id,
            lo.observation_datetime,
            l.elevation AS elevation_m,
            lo.depth_to_water_below_ground_surface AS depth_to_water_below_ground_surface_ft,
            ((l.elevation * {METERS_TO_FEET}) - lo.depth_to_water_below_ground_surface)
                AS water_elevation_ft,
            l.point
        FROM latest_obs AS lo
        JOIN thing AS t ON t.id = lo.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE lo.rn = 1
    """


def _create_actively_monitored_wells_view() -> str:
    # No predicate of its own -- inherits whatever rows
    # ogc_internal_water_well_summary exposes (here, all of them)
    # transitively via the JOIN below. Mirrors the public side's
    # ogc_actively_monitored_wells, which likewise never filters on
    # status_history.release_status directly (see
    # w1x2y3z4a5b6_drop_child_release_filters_from_ngwmn_views.py for why).
    return """
        CREATE VIEW ogc_internal_actively_monitored_wells AS
        WITH latest_monitoring_status AS (
            SELECT DISTINCT ON (sh.target_id)
                sh.target_id AS thing_id,
                sh.status_value
            FROM status_history AS sh
            WHERE
                sh.target_table = 'thing'
                AND sh.status_type = 'Monitoring Status'
            ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
        )
        SELECT
            wws.id,
            wws.name,
            'water well'::text AS thing_type,
            wws.well_depth,
            wws.elevation,
            wws.elevation_method,
            wws.formation_zone,
            wws.total_water_levels,
            wws.last_water_level,
            wws.last_water_level_datetime,
            wws.min_water_level,
            wws.max_water_level,
            wws.water_level_trend_ft_per_year,
            g.id AS group_id,
            g.name AS group_name,
            g.group_type,
            wws.point
        FROM "group" AS g
        JOIN group_thing_association AS gta ON gta.group_id = g.id
        JOIN ogc_internal_water_well_summary AS wws ON wws.id = gta.thing_id
        JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
        WHERE lower(trim(g.name)) = 'water level network'
          AND lms.status_value = 'Currently monitored'
    """


def _create_project_areas_view(public_only: bool) -> str:
    release_filter = " AND g.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW ogc_internal_project_areas AS
        SELECT
            g.id,
            g.name,
            g.description,
            g.group_type,
            g.release_status,
            g.project_area
        FROM "group" AS g
        WHERE g.project_area IS NOT NULL{release_filter}
    """


def _create_locations_view() -> str:
    # Unlike ogc_locations (always public-only, even on the public side's
    # downgrade path), ogc_internal_locations has no release_status
    # predicate at all -- the internal mount is unfiltered by design, and
    # this relation never existed in any form before this migration.
    # Column list matches ogc_locations exactly; see
    # f4a5b6c7d8e9_apply_public_release_status_filter_to_ogc_views.py's
    # _create_locations_view() for the db/location.py column verification.
    return """
        CREATE VIEW ogc_internal_locations AS
        SELECT
            l.id,
            l.nma_pk_location,
            l.description,
            l.county,
            l.state,
            l.quad_name,
            l.nma_location_notes,
            l.nma_coordinate_notes,
            l.nma_data_reliability,
            l.nma_date_created,
            l.nma_site_date,
            l.release_status,
            l.elevation,
            l.point
        FROM location AS l
    """


# Shared join from a thing to its current location point -- same shape as
# z9a0b1c2d3e4's _LOCATION_JOIN.
_EDR_LOCATION_JOIN = """
    JOIN location_thing_association lta
        ON lta.thing_id = t.id AND lta.effective_end IS NULL
    JOIN location l ON l.id = lta.location_id
"""


def _create_internal_waterlevels_view() -> str:
    # Mirrors z9a0b1c2d3e4's ogc_waterlevels with both release_status
    # predicates dropped (manual readings: o.release_status; transducer
    # readings: tobs.release_status). release_status itself is still
    # selected as a column, same as the public view.
    return f"""
        CREATE VIEW ogc_internal_waterlevels AS
        -- manual water-level readings
        SELECT
            'm-' || o.id                        AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            o.observation_datetime              AS datetime,
            o.value                             AS value,
            o.unit                              AS unit,
            'groundwater level'                 AS parameter_name,
            'manual'                            AS source,
            NULL::integer                       AS deployment_id,
            o.release_status                    AS release_status
        FROM observation o
        JOIN parameter p
            ON p.id = o.parameter_id AND p.parameter_name = 'groundwater level'
        JOIN sample sm ON sm.id = o.sample_id
        JOIN field_activity fa ON fa.id = sm.field_activity_id
        JOIN field_event fe ON fe.id = fa.field_event_id
        JOIN thing t ON t.id = fe.thing_id
        {_EDR_LOCATION_JOIN}
        WHERE o.value IS NOT NULL

        UNION ALL

        -- transducer (instrument) water-level readings
        SELECT
            't-' || tobs.id                     AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            tobs.observation_datetime           AS datetime,
            tobs.value                          AS value,
            p.default_unit                      AS unit,
            'groundwater level'                 AS parameter_name,
            'transducer'                        AS source,
            tobs.deployment_id                  AS deployment_id,
            tobs.release_status                 AS release_status
        FROM transducer_observation tobs
        JOIN parameter p
            ON p.id = tobs.parameter_id AND p.parameter_name = 'groundwater level'
        JOIN deployment d ON d.id = tobs.deployment_id
        JOIN thing t ON t.id = d.thing_id
        {_EDR_LOCATION_JOIN}
        WHERE tobs.value IS NOT NULL
    """


def _create_internal_water_chemistry_view() -> str:
    # Mirrors z9a0b1c2d3e4's ogc_water_chemistry with its release_status
    # predicate (o.release_status) dropped.
    return f"""
        CREATE VIEW ogc_internal_water_chemistry AS
        SELECT
            'c-' || o.id                        AS id,
            t.id                                AS thing_id,
            t.name                              AS station_name,
            ST_X(l.point)                       AS longitude,
            ST_Y(l.point)                       AS latitude,
            o.observation_datetime              AS datetime,
            o.value                             AS value,
            o.unit                              AS unit,
            p.parameter_name                    AS parameter_name,
            o.sample_id                         AS sample_id,
            o.release_status                    AS release_status
        FROM observation o
        JOIN parameter p
            ON p.id = o.parameter_id AND p.parameter_name <> 'groundwater level'
        JOIN sample sm ON sm.id = o.sample_id
        JOIN field_activity fa ON fa.id = sm.field_activity_id
        JOIN field_event fe ON fe.id = fa.field_event_id
        JOIN thing t ON t.id = fe.thing_id
        {_EDR_LOCATION_JOIN}
        WHERE o.value IS NOT NULL
    """


def _recreate_all_internal_views() -> None:
    # ogc_internal_actively_monitored_wells depends on
    # ogc_internal_water_well_summary via a direct JOIN; Postgres refuses to
    # drop a materialized view while a dependent view exists, so it must go
    # first and come back last -- same ordering constraint as the public side.
    _drop_view_or_materialized_view("ogc_internal_actively_monitored_wells")

    for view_id, thing_type in THING_VIEWS:
        _drop_view_or_materialized_view(f"ogc_internal_{_safe_view_id(view_id)}")
        op.execute(text(_create_thing_view(view_id, thing_type, public_only=False)))

    _drop_view_or_materialized_view("ogc_internal_latest_depth_to_water_wells")
    op.execute(text(_create_latest_depth_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_latest_depth_to_water_wells IS "
            "'Unfiltered latest depth-to-water per well view for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_latest_depth_to_water_wells_id "
            "ON ogc_internal_latest_depth_to_water_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_avg_tds_wells")
    op.execute(text(_create_avg_tds_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_avg_tds_wells IS "
            "'Unfiltered average TDS per well from major chemistry results for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_avg_tds_wells_id "
            "ON ogc_internal_avg_tds_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_latest_tds_wells")
    op.execute(text(_create_latest_tds_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_latest_tds_wells IS "
            "'Unfiltered latest TDS per well from major chemistry results for the internal pygeoapi mount.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_depth_to_water_trend_wells")
    op.execute(text(_create_depth_to_water_trend_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_depth_to_water_trend_wells IS "
            "'Unfiltered depth-to-water trend classification for water wells, for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_depth_to_water_trend_wells_id "
            "ON ogc_internal_depth_to_water_trend_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_water_well_summary")
    op.execute(text(_create_water_well_summary_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_water_well_summary IS "
            "'Unfiltered summary statistics for water wells including water-level trend, for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_water_well_summary_id "
            "ON ogc_internal_water_well_summary (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_major_chemistry_results")
    op.execute(text(_create_major_chemistry_results_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_major_chemistry_results IS "
            "'Unfiltered latest major-chemistry analyte values per location, pivoted into static analyte columns, for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_major_chemistry_results_id "
            "ON ogc_internal_major_chemistry_results (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_minor_chemistry_wells")
    op.execute(text(_create_minor_chemistry_wells_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_minor_chemistry_wells IS "
            "'Unfiltered latest minor/trace chemistry analyte values for water wells, pivoted into static analyte columns, for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_minor_chemistry_wells_id "
            "ON ogc_internal_minor_chemistry_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_water_elevation_wells")
    op.execute(text(_create_water_elevation_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_internal_water_elevation_wells IS "
            "'Unfiltered latest water elevation per well with explicit units: "
            "elevation_m, depth_to_water_below_ground_surface_ft, water_elevation_ft, for the internal pygeoapi mount.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_internal_water_elevation_wells_id "
            "ON ogc_internal_water_elevation_wells (id)"
        )
    )

    # Recreate now that ogc_internal_water_well_summary exists again.
    op.execute(text(_create_actively_monitored_wells_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_actively_monitored_wells IS "
            "'Unfiltered wells in the Water Level Network group, for the internal pygeoapi mount.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_project_areas")
    op.execute(text(_create_project_areas_view(public_only=False)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_project_areas IS "
            "'Unfiltered project areas for groups with polygon boundaries, for the internal pygeoapi mount.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_locations")
    op.execute(text(_create_locations_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_locations IS "
            "'Unfiltered locations for the internal pygeoapi mount.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_waterlevels")
    op.execute(text(_create_internal_waterlevels_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_waterlevels IS "
            "'Unfiltered depth-to-water readings (manual + transducer) for the internal pygeoapi mount.'"
        )
    )

    _drop_view_or_materialized_view("ogc_internal_water_chemistry")
    op.execute(text(_create_internal_water_chemistry_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_internal_water_chemistry IS "
            "'Unfiltered water-chemistry analyses (by analyte) for the internal pygeoapi mount.'"
        )
    )


# All 24 relations this migration creates, in an order safe for DROP (the
# dependent view first, mirroring _recreate_all_internal_views's ordering).
ALL_INTERNAL_RELATIONS = [
    "ogc_internal_actively_monitored_wells",
    *[f"ogc_internal_{view_id}" for view_id, _ in THING_VIEWS],
    "ogc_internal_latest_depth_to_water_wells",
    "ogc_internal_avg_tds_wells",
    "ogc_internal_latest_tds_wells",
    "ogc_internal_depth_to_water_trend_wells",
    "ogc_internal_water_well_summary",
    "ogc_internal_major_chemistry_results",
    "ogc_internal_minor_chemistry_wells",
    "ogc_internal_water_elevation_wells",
    "ogc_internal_project_areas",
    "ogc_internal_locations",
    "ogc_internal_waterlevels",
    "ogc_internal_water_chemistry",
]


def upgrade() -> None:
    _check_required_tables()
    _recreate_all_internal_views()


def downgrade() -> None:
    # None of these 24 relations existed before this migration -- unlike
    # f4a5b6c7d8e9's downgrade (which recreates the prior unfiltered public
    # views), there is no prior state to restore, so downgrade just drops
    # everything this migration created.
    for relation in ALL_INTERNAL_RELATIONS:
        _drop_view_or_materialized_view(relation)
