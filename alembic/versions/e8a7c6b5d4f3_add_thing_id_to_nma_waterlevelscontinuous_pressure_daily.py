"""Add thing_id FK to NMA_WaterLevelsContinuous_Pressure_Daily.

Revision ID: e8a7c6b5d4f3
Revises: b12e3919077e
Create Date: 2026-01-29 12:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "e8a7c6b5d4f3"
down_revision: Union[str, Sequence[str], None] = "b12e3919077e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add thing_id and FK to legacy pressure daily table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_WaterLevelsContinuous_Pressure_Daily"):
        return

    columns = {
        col["name"]
        for col in inspector.get_columns("NMA_WaterLevelsContinuous_Pressure_Daily")
    }
    if "thing_id" not in columns:
        op.add_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            sa.Column("thing_id", sa.Integer(), nullable=True),
        )

    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("NMA_WaterLevelsContinuous_Pressure_Daily")
        if fk.get("name")
    }
    if "fk_pressure_daily_thing" not in existing_fks:
        op.create_foreign_key(
            "fk_pressure_daily_thing",
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "thing",
            ["thing_id"],
            ["id"],
            ondelete="CASCADE",
        )

    null_count = bind.execute(
        sa.text(
            'SELECT COUNT(*) FROM "NMA_WaterLevelsContinuous_Pressure_Daily" '
            'WHERE "thing_id" IS NULL'
        )
    ).scalar()
    if null_count == 0:
        op.alter_column(
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            "thing_id",
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade() -> None:
    """Remove thing_id FK from legacy pressure daily table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_WaterLevelsContinuous_Pressure_Daily"):
        return

    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("NMA_WaterLevelsContinuous_Pressure_Daily")
        if fk.get("name")
    }
    if "fk_pressure_daily_thing" in existing_fks:
        op.drop_constraint(
            "fk_pressure_daily_thing",
            "NMA_WaterLevelsContinuous_Pressure_Daily",
            type_="foreignkey",
        )

    columns = {
        col["name"]
        for col in inspector.get_columns("NMA_WaterLevelsContinuous_Pressure_Daily")
    }
    if "thing_id" in columns:
        op.drop_column("NMA_WaterLevelsContinuous_Pressure_Daily", "thing_id")
