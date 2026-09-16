"""exclude embargoed records from the public water-level OGC views

The four public relations that read the observation chain gate on the thing's
release_status and nothing below it, so an embargoed observation at a public
well would still be published. This adds the missing clause to each.

**Why `IS DISTINCT FROM 'embargoed'` and not `= 'public'`.** The other
observation-backed public relations (ogc_well_water_column, and the Group A
thing views since b8c9d0e1f2a3) filter their observations on
`release_status = 'public'`. Matching them here would be tidier and is
deliberately not done: it would also drop every observation sitting at
`draft`, `provisional`, or NULL, which is a release-policy change with its own
row counts to check, not an embargo. This predicate removes exactly the
embargoed rows, of which there are none until somebody sets one, so the four
relations return byte-identical results the day this lands. Migration
w1x2y3z4a5b6 is the record of what the tidier version costs when the row
states are not what you assumed: three NGWMN exports emptied, 3005/3005 rows.

`IS DISTINCT FROM` rather than `<>` because release_status is nullable, and
`NULL <> 'embargoed'` is NULL, which would filter the row out -- turning a
narrow embargo clause into exactly the silent emptying above.

Whole-thing embargoes need no change: `t.release_status = 'public'` already
excludes 'embargoed', so a thing held back disappears from every public
relation the moment its level changes.

The chemistry collections are untouched and cannot be fixed here.
ogc_major_chemistry_results, ogc_minor_chemistry_wells, ogc_avg_tds_wells and
ogc_latest_tds_wells read the legacy NMA_* mirror tables, which carry no
release columns at all -- their only gate is the joined thing. Per-record
chemistry embargo is a separate decision; see docs/data-embargo.md.

Only public relations change. The ogc_internal_* mount serves Bureau staff and
has never filtered on release_status; seeing embargoed data before it is
published is the point of it.

The view bodies below are character-for-character the templates from
f4a5b6c7d8e9 (and 986e0eb85ab3 for ogc_actively_monitored_wells) with the
embargo clause added; downgrade() restores them without it.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
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
}

# These relations only exist in their public-filtered form, so the thing-level
# clause is no longer a toggle -- it is always emitted, and only the embargo
# clause below is switched between upgrade and downgrade.
PUBLIC_FILTER = " AND t.release_status = 'public'"

# One clause per level of the chain the CTEs join: observation, sample,
# activity, event. Indented to the 16 columns the surrounding WHERE clauses
# use, since it is interpolated into the middle of them.
EMBARGO_ALIASES = ("o", "s", "fa", "fe")
EMBARGO_FILTER = "".join(
    f"\n{' ' * 16}AND {alias}.release_status IS DISTINCT FROM 'embargoed'"
    for alias in EMBARGO_ALIASES
)

METERS_TO_FEET = 3.28084

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()


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
            "Cannot apply the embargo filter to the OGC views. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_latest_depth_view(with_embargo: bool) -> str:
    release_filter = PUBLIC_FILTER + (EMBARGO_FILTER if with_embargo else "")
    return f"""
        CREATE MATERIALIZED VIEW ogc_latest_depth_to_water_wells AS
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


def _create_depth_to_water_trend_view(with_embargo: bool) -> str:
    release_filter = PUBLIC_FILTER + (EMBARGO_FILTER if with_embargo else "")
    return f"""
        CREATE MATERIALIZED VIEW ogc_depth_to_water_trend_wells AS
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


def _create_water_well_summary_view(with_embargo: bool) -> str:
    release_filter = PUBLIC_FILTER + (EMBARGO_FILTER if with_embargo else "")
    return f"""
        CREATE MATERIALIZED VIEW ogc_water_well_summary AS
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


def _create_water_elevation_view(with_embargo: bool) -> str:
    release_filter = PUBLIC_FILTER + (EMBARGO_FILTER if with_embargo else "")
    return f"""
        CREATE MATERIALIZED VIEW ogc_water_elevation_wells AS
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


def _create_actively_monitored_wells_view(all_groups: bool) -> str:
    if all_groups:
        # Aggregated: one row per well, group_ids/group_names/group_types as
        # arrays, so `id` stays unique even when a well belongs to several
        # groups. release_status = 'public' is checked on the group row
        # itself (mirrors _create_project_areas_view's public_only handling)
        # since any group can appear here now, not just one hardcoded one.
        # group_thing_association has no unique constraint on
        # (group_id, thing_id), so distinct_memberships de-dupes before
        # aggregating; all three arrays are ordered by the same group_id key
        # so they stay index-aligned with each other (ordering each array by
        # its own column, e.g. names alphabetically, would desync them).
        return """
            CREATE VIEW ogc_actively_monitored_wells AS
            WITH latest_monitoring_status AS (
                SELECT DISTINCT ON (sh.target_id)
                    sh.target_id AS thing_id,
                    sh.status_value
                FROM status_history AS sh
                WHERE
                    sh.target_table = 'thing'
                    AND sh.status_type = 'Monitoring Status'
                ORDER BY sh.target_id, sh.start_date DESC, sh.id DESC
            ),
            distinct_memberships AS (
                SELECT DISTINCT
                    gta.thing_id,
                    g.id AS group_id,
                    g.name AS group_name,
                    g.group_type
                FROM group_thing_association AS gta
                JOIN "group" AS g ON g.id = gta.group_id
                WHERE g.release_status = 'public'
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
                array_agg(dm.group_id ORDER BY dm.group_id) AS group_ids,
                array_agg(dm.group_name ORDER BY dm.group_id) AS group_names,
                array_agg(dm.group_type ORDER BY dm.group_id) AS group_types,
                wws.point
            FROM ogc_water_well_summary AS wws
            JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
            JOIN distinct_memberships AS dm ON dm.thing_id = wws.id
            WHERE lms.status_value = 'Currently monitored'
            GROUP BY
                wws.id, wws.name, wws.well_depth, wws.elevation,
                wws.elevation_method, wws.formation_zone,
                wws.total_water_levels, wws.last_water_level,
                wws.last_water_level_datetime, wws.min_water_level,
                wws.max_water_level, wws.water_level_trend_ft_per_year,
                wws.point
        """
    # Historical (downgrade target): byte-for-byte the pre-fix view, single
    # group_id/group_name/group_type columns, scoped to one hardcoded group.
    return """
        CREATE VIEW ogc_actively_monitored_wells AS
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
        JOIN ogc_water_well_summary AS wws ON wws.id = gta.thing_id
        JOIN latest_monitoring_status AS lms ON lms.thing_id = wws.id
        WHERE lower(trim(g.name)) = 'water level network'
          AND lms.status_value = 'Currently monitored'
    """


def _recreate_water_level_views(with_embargo: bool) -> None:
    """Rebuild the four observation-backed relations, embargo clause on or off.

    ogc_actively_monitored_wells depends on ogc_water_well_summary via a direct
    JOIN; Postgres refuses to drop a materialized view while a dependent view
    exists, so it goes first and comes back last. It is recreated from
    986e0eb85ab3's all-groups form -- the shape in production -- not
    f4a5b6c7d8e9's, and its own SQL is unchanged: it inherits the embargo
    filter through the summary it selects from.
    """
    _drop_view_or_materialized_view("ogc_actively_monitored_wells")

    _drop_view_or_materialized_view("ogc_latest_depth_to_water_wells")
    op.execute(text(_create_latest_depth_view(with_embargo)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_latest_depth_to_water_wells IS "
            "'Latest depth-to-water per well view for pygeoapi.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_latest_depth_to_water_wells_id "
            "ON ogc_latest_depth_to_water_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_depth_to_water_trend_wells")
    op.execute(text(_create_depth_to_water_trend_view(with_embargo)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_depth_to_water_trend_wells IS "
            "'Depth-to-water trend classification for water wells.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_depth_to_water_trend_wells_id "
            "ON ogc_depth_to_water_trend_wells (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_water_well_summary")
    op.execute(text(_create_water_well_summary_view(with_embargo)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_water_well_summary IS "
            "'Summary statistics for water wells including water-level trend.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_water_well_summary_id "
            "ON ogc_water_well_summary (id)"
        )
    )

    _drop_view_or_materialized_view("ogc_water_elevation_wells")
    op.execute(text(_create_water_elevation_view(with_embargo)))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_water_elevation_wells IS "
            "'Latest water elevation per well with explicit units: "
            "elevation_m, depth_to_water_below_ground_surface_ft, water_elevation_ft.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_water_elevation_wells_id "
            "ON ogc_water_elevation_wells (id)"
        )
    )

    # Recreate now that ogc_water_well_summary exists again.
    op.execute(text(_create_actively_monitored_wells_view(all_groups=True)))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_actively_monitored_wells IS "
            "'Actively (currently) monitored wells across all groups for pygeoapi.'"
        )
    )


def upgrade() -> None:
    _check_required_tables()
    _recreate_water_level_views(with_embargo=True)


def downgrade() -> None:
    _recreate_water_level_views(with_embargo=False)
