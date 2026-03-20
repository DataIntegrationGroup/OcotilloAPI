"""add actively monitored wells pygeoapi view

Revision ID: r2s3t4u5v6w7
Revises: p9c0d1e2f3a4
Create Date: 2026-03-19 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, Sequence[str], None] = "p9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
DROP_VIEW_SQL = "DROP VIEW IF EXISTS ogc_actively_monitored_wells"
DROP_MATVIEW_SQL = "DROP MATERIALIZED VIEW IF EXISTS " "ogc_actively_monitored_wells"


def _create_actively_monitored_wells_view() -> str:
    return """
        CREATE VIEW ogc_actively_monitored_wells AS
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
        WHERE lower(trim(g.name)) = 'water level network'
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    required_tables = {
        "group",
        "group_thing_association",
    }

    if not required_tables.issubset(existing_tables):
        missing = sorted(
            table_name
            for table_name in required_tables
            if table_name not in existing_tables
        )
        raise RuntimeError(
            "Cannot create ogc_actively_monitored_wells. "
            f"Missing required tables: {', '.join(missing)}"
        )

    has_summary = bind.execute(
        text(
            "SELECT 1 FROM pg_matviews "
            "WHERE schemaname = 'public' "
            "AND matviewname = 'ogc_water_well_summary'"
        )
    ).scalar()
    if has_summary != 1:
        raise RuntimeError(
            "Cannot create ogc_actively_monitored_wells. "
            "Missing required materialized view: ogc_water_well_summary"
        )

    op.execute(text(DROP_VIEW_SQL))
    op.execute(text(DROP_MATVIEW_SQL))
    op.execute(text(_create_actively_monitored_wells_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_actively_monitored_wells IS "
            "'Wells in the Water Level Network group for pygeoapi.'"
        )
    )


def downgrade() -> None:
    op.execute(text(DROP_VIEW_SQL))
    op.execute(text(DROP_MATVIEW_SQL))
