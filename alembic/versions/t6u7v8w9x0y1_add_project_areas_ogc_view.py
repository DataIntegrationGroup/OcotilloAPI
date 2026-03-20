"""add project areas OGC view

Revision ID: t6u7v8w9x0y1
Revises: s4t5u6v7w8x9
Create Date: 2026-03-19 16:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "t6u7v8w9x0y1"
down_revision: Union[str, Sequence[str], None] = "s4t5u6v7w8x9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DROP_VIEW_SQL = "DROP VIEW IF EXISTS ogc_project_areas"


def _create_project_areas_view() -> str:
    return """
        CREATE VIEW ogc_project_areas AS
        SELECT
            g.id,
            g.name,
            g.description,
            g.group_type,
            g.release_status,
            g.project_area
        FROM "group" AS g
        WHERE g.project_area IS NOT NULL
    """


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public"))
    if "group" not in existing_tables:
        raise RuntimeError(
            "Cannot create ogc_project_areas. Missing required table: group"
        )

    group_columns = {column["name"] for column in inspector.get_columns("group")}
    if "project_area" not in group_columns:
        raise RuntimeError(
            "Cannot create ogc_project_areas. "
            "Missing required column: group.project_area"
        )

    op.execute(text(DROP_VIEW_SQL))
    op.execute(text(_create_project_areas_view()))
    op.execute(
        text(
            "COMMENT ON VIEW ogc_project_areas IS "
            "'Project areas for groups with polygon boundaries for pygeoapi.'"
        )
    )


def downgrade() -> None:
    op.execute(text(DROP_VIEW_SQL))
