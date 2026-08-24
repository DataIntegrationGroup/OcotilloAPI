"""add the well water-column OGC layer

A water well's construction record says how deep the hole goes; its
groundwater-level record says how far down the water sits. The difference --
the standing column of water inside the well -- is the number that says whether
a well still has usable water in it, and nothing in the catalogue published it.

This creates ogc_well_water_column (public) and ogc_internal_well_water_column
(unfiltered), one row per water well, carrying the same well and location
fields the water_wells layer publishes plus four derived depths, all in feet:

    water_column_latest    well depth minus the most recent depth to water
    water_column_average   well depth minus the mean depth to water
    water_column_maximum   well depth minus the shallowest depth to water
    water_column_minimum   well depth minus the deepest depth to water

Shallowest water gives the largest column and deepest water the smallest, hence
the maximum/minimum naming: these are the extremes of the water column itself,
not of the readings behind them.

Readings are manual groundwater-level observations, taken below ground surface
as (value - measuring_point_height) with a missing height treated as ground
level -- the same convention as ogc_water_well_summary and
ogc_latest_depth_to_water_wells, so the three layers cannot disagree about what
a depth to water is. Continuous transducer readings are not included.

Negative results are clamped to zero. A reading deeper than the recorded well
depth is a contradiction between two records rather than a well holding
negative water, and the clamp keeps consumers from having to special-case it;
the contradiction itself stays visible in water_well_summary, which publishes
the raw shallowest and deepest readings next to the well depth.

Rows are restricted to wells that have both a well depth and at least one
usable reading -- without either, all four columns would be NULL and the row
would say nothing.

Materialized, because every column but the latest one aggregates a well's
entire reading history. The nightly pg_cron job (b6c7d8e9f0a1) refreshes every
matview in the public schema by name, so these two are picked up with no change
to the schedule. Both carry a unique index on id so the refresh can also be run
CONCURRENTLY by hand (`oco refresh-matview --concurrently`).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-24 00:00:00.000000
"""

import re
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
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

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()

VIEWS = [
    ("ogc_well_water_column", True),
    ("ogc_internal_well_water_column", False),
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
            "Cannot create the well water-column views. "
            f"Missing required tables: {', '.join(sorted(missing))}"
        )


def _create_well_water_column_view(view_name: str, public_only: bool) -> str:
    safe_view_name = _safe_relation_name(view_name)
    release_filter = " AND t.release_status = 'public'" if public_only else ""
    observation_release_filter = (
        "\n                  AND o.release_status = 'public'" if public_only else ""
    )
    return f"""
        CREATE MATERIALIZED VIEW {safe_view_name} AS
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
                AND o.observation_datetime IS NOT NULL{observation_release_filter}
        ),
        wl_agg AS (
            SELECT
                w.thing_id,
                AVG(w.water_level) AS avg_water_level,
                MIN(w.water_level) AS min_water_level,
                MAX(w.water_level) AS max_water_level
            FROM wl_obs AS w
            GROUP BY w.thing_id
        ),
        wl_last AS (
            SELECT
                ranked.thing_id,
                ranked.water_level AS last_water_level
            FROM (
                SELECT
                    w.thing_id,
                    w.water_level,
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
            GREATEST(t.well_depth - wl.last_water_level, 0) AS water_column_latest,
            GREATEST(t.well_depth - wa.avg_water_level, 0) AS water_column_average,
            -- The shallowest reading leaves the most water in the well, the
            -- deepest the least, so min/max swap sides here.
            GREATEST(t.well_depth - wa.min_water_level, 0) AS water_column_maximum,
            GREATEST(t.well_depth - wa.max_water_level, 0) AS water_column_minimum,
            l.elevation,
            l.point
        FROM thing AS t
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        JOIN wl_agg AS wa ON wa.thing_id = t.id
        JOIN wl_last AS wl ON wl.thing_id = t.id
        WHERE
            t.thing_type = 'water well'
            AND t.well_depth IS NOT NULL{release_filter}
    """


def upgrade() -> None:
    _check_required_tables()

    for view_name, public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {safe_view_name}"))
        op.execute(text(_create_well_water_column_view(view_name, public_only)))
        # Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
        op.execute(
            text(
                f"CREATE UNIQUE INDEX ix_{safe_view_name}_id "
                f"ON {safe_view_name} (id)"
            )
        )


def downgrade() -> None:
    for view_name, _public_only in VIEWS:
        safe_view_name = _safe_relation_name(view_name)
        op.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {safe_view_name}"))
