"""add water well summary materialized view

Revision ID: l5e6f7a8b9c0
Revises: k4d5e6f7a8b9
Create Date: 2026-03-02 20:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "l5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "k4d5e6f7a8b9"
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


def _create_water_well_summary_view() -> str:
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
                AND o.observation_datetime IS NOT NULL
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
        "data_provenance",
    }

    if not required_tables.issubset(existing_tables):
        missing = sorted(t for t in required_tables if t not in existing_tables)
        raise RuntimeError(
            "Cannot create ogc_water_well_summary. Missing required tables: "
            + ", ".join(missing)
        )

    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_water_well_summary"))
    op.execute(text(_create_water_well_summary_view()))
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


def downgrade() -> None:
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS ogc_water_well_summary"))
