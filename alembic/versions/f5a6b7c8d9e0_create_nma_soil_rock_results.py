"""Create legacy NMA_Soil_Rock_Results table.

Revision ID: f5a6b7c8d9e0
Revises: e4b5c6d7e8f9
Create Date: 2026-03-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy soil/rock results table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_Soil_Rock_Results"):
        op.create_table(
            "NMA_Soil_Rock_Results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("Point_ID", sa.String(length=255), nullable=True),
            sa.Column("Sample Type", sa.String(length=255), nullable=True),
            sa.Column("Date Sampled", sa.String(length=255), nullable=True),
            sa.Column("d13C", sa.Float(), nullable=True),
            sa.Column("d18O", sa.Float(), nullable=True),
            sa.Column("Sampled by", sa.String(length=255), nullable=True),
        )
        op.create_index(
            "Soil_Rock_Results$Point_ID", "NMA_Soil_Rock_Results", ["Point_ID"]
        )


def downgrade() -> None:
    """Drop the legacy soil/rock results table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_Soil_Rock_Results"):
        op.drop_table("NMA_Soil_Rock_Results")
