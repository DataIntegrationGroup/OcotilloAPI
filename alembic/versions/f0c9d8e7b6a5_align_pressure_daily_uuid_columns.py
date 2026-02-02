"""Align UUID column types on NMA_WaterLevelsContinuous_Pressure_Daily.

Revision ID: f0c9d8e7b6a5
Revises: e8a7c6b5d4f3
Create Date: 2026-01-29 12:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f0c9d8e7b6a5"
down_revision: Union[str, Sequence[str], None] = "e8a7c6b5d4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_is_uuid(col) -> bool:
    return isinstance(col.get("type"), postgresql.UUID)


def upgrade() -> None:
    """Alter UUID columns to proper UUID types."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_WaterLevelsContinuous_Pressure_Daily"):
        return

    columns = {
        col["name"]: col
        for col in inspector.get_columns("NMA_WaterLevelsContinuous_Pressure_Daily")
    }

    global_id_col = columns.get("GlobalID")
    if global_id_col is not None and not _column_is_uuid(global_id_col):
        op.alter_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "GlobalID",
            type_=postgresql.UUID(as_uuid=True),
            postgresql_using='"GlobalID"::uuid',
        )

    well_id_col = columns.get("WellID")
    if well_id_col is not None and not _column_is_uuid(well_id_col):
        op.alter_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "WellID",
            type_=postgresql.UUID(as_uuid=True),
            postgresql_using='"WellID"::uuid',
        )


def downgrade() -> None:
    """Revert UUID columns back to strings."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_WaterLevelsContinuous_Pressure_Daily"):
        return

    columns = {
        col["name"]: col
        for col in inspector.get_columns("NMA_WaterLevelsContinuous_Pressure_Daily")
    }

    global_id_col = columns.get("GlobalID")
    if global_id_col is not None and _column_is_uuid(global_id_col):
        op.alter_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "GlobalID",
            type_=sa.String(length=40),
            postgresql_using='"GlobalID"::text',
        )

    well_id_col = columns.get("WellID")
    if well_id_col is not None and _column_is_uuid(well_id_col):
        op.alter_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "WellID",
            type_=sa.String(length=40),
            postgresql_using='"WellID"::text',
        )
