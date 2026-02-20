"""Make NMA_SurfaceWaterData.thing_id nullable.

Revision ID: i2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-02-20 17:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "i2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow orphan legacy SurfaceWaterData rows without a mapped Thing."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_SurfaceWaterData"):
        return

    columns = {col["name"] for col in inspector.get_columns("NMA_SurfaceWaterData")}
    if "thing_id" not in columns:
        return

    op.alter_column(
        "NMA_SurfaceWaterData",
        "thing_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Revert to NOT NULL only when no null thing_id values exist."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_SurfaceWaterData"):
        return

    columns = {col["name"] for col in inspector.get_columns("NMA_SurfaceWaterData")}
    if "thing_id" not in columns:
        return

    op.execute('DELETE FROM "NMA_SurfaceWaterData" WHERE thing_id IS NULL')
    op.alter_column(
        "NMA_SurfaceWaterData",
        "thing_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
