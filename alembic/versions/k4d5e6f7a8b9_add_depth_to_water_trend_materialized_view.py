"""add depth to water trend materialized view

Revision ID: k4d5e6f7a8b9
Revises: i2b3c4d5e6f7
Create Date: 2026-03-02 19:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "k4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "i2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LATEST_LOCATION_CTE = """
SELECT DISTINCT ON (lta.thing_id)
    lta.thing_id,
    lta.location_id,
    lta.effective_start
FROM location_thing_association AS lta
WHERE lta.effective_end IS NULL
ORDER BY lta.thing_id, lta.effective_start DESC
""".strip()


def _create_depth_to_water_trend_view() -> str:
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
                AND o.observation_datetime IS NOT NULL
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
            "Cannot create ogc_depth_to_water_trend_wells. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_depth_to_water_trend_wells"))
    op.execute(text(_create_depth_to_water_trend_view()))
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


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_depth_to_water_trend_wells"))
