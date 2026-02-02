"""Add unique constraint for NMA_WaterLevelsContinuous_Pressure_Daily

Revision ID: 4b7aa74b15ad
Revises: 8a1de3e3f0b3
Create Date: 2026-02-10 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b7aa74b15ad"
down_revision: Union[str, Sequence[str], None] = "8a1de3e3f0b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ensure unique constraint on GlobalID for upserts."""
    op.create_unique_constraint(
        "uq_nma_pressure_daily_globalid",
        "NMA_WaterLevelsContinuous_Pressure_Daily",
        ["GlobalID"],
    )


def downgrade() -> None:
    """Drop the unique constraint."""
    op.drop_constraint(
        "uq_nma_pressure_daily_globalid",
        "NMA_WaterLevelsContinuous_Pressure_Daily",
        type_="unique",
    )
