"""fix water elevation units to feet

Revision ID: n7a8b9c0d1e2
Revises: m6f7a8b9c0d1
Create Date: 2026-03-10 11:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "n7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "m6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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


def _create_water_elevation_view() -> str:
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
                )
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


def _create_water_elevation_view_m6() -> str:
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
                (o.value - COALESCE(o.measuring_point_height, 0))
                    AS depth_to_water_below_ground_surface,
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
                AND o.value IS NOT NULL
                AND o.observation_datetime IS NOT NULL
        )
        SELECT
            t.id AS id,
            t.name,
            t.thing_type,
            ro.observation_id,
            ro.observation_datetime,
            l.elevation,
            ro.depth_to_water_below_ground_surface,
            (
                l.elevation - ro.depth_to_water_below_ground_surface
            ) AS water_elevation,
            l.point
        FROM ranked_obs AS ro
        JOIN thing AS t ON t.id = ro.thing_id
        JOIN latest_location AS ll ON ll.thing_id = t.id
        JOIN location AS l ON l.id = ll.location_id
        WHERE ro.rn = 1
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    required_tables = {
        "thing",
        "location",
        "location_thing_association",
        "observation",
        "sample",
        "field_activity",
        "field_event",
    }

    if not required_tables.issubset(existing_tables):
        missing = sorted(t for t in required_tables if t not in existing_tables)
        raise RuntimeError(
            "Cannot create ogc_water_elevation_wells. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_water_elevation_wells"))
    op.execute(text(_create_water_elevation_view()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_water_elevation_wells IS "
            "'Latest water elevation per well with explicit units: elevation_m, depth_to_water_below_ground_surface_ft, water_elevation_ft.'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_water_elevation_wells_id "
            "ON ogc_water_elevation_wells (id)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_water_elevation_wells"))
    op.execute(text(_create_water_elevation_view_m6()))
    op.execute(
        text(
            "COMMENT ON MATERIALIZED VIEW ogc_water_elevation_wells IS "
            "'Latest water elevation per well (elevation minus depth to water below ground surface).'"
        )
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ux_ogc_water_elevation_wells_id "
            "ON ogc_water_elevation_wells (id)"
        )
    )
