"""Create legacy NMAWaterLevelsContinuousPressureDaily table.

Revision ID: 7c02d9f8f412
Revises: 2101e0b029dc
Create Date: 2026-01-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7c02d9f8f412"
down_revision: Union[str, Sequence[str], None] = "2101e0b029dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy daily pressure table used for backfill."""
    op.create_table(
        "NMA_WaterLevelsContinuous_Pressure_Daily",
        sa.Column("GlobalID", sa.String(length=40), primary_key=True),
        sa.Column("OBJECTID", sa.Integer(), autoincrement=True, nullable=True),
        sa.Column("WellID", sa.String(length=40), nullable=True),
        sa.Column("PointID", sa.String(length=50), nullable=True),
        sa.Column("DateMeasured", sa.DateTime(), nullable=False),
        sa.Column("TemperatureWater", sa.Float(), nullable=True),
        sa.Column("WaterHead", sa.Float(), nullable=True),
        sa.Column("WaterHeadAdjusted", sa.Float(), nullable=True),
        sa.Column("DepthToWaterBGS", sa.Float(), nullable=True),
        sa.Column("MeasurementMethod", sa.String(length=2), nullable=True),
        sa.Column("DataSource", sa.String(length=5), nullable=True),
        sa.Column("MeasuringAgency", sa.String(length=50), nullable=True),
        sa.Column("QCed", sa.Boolean(), nullable=True),
        sa.Column("Notes", sa.String(length=100), nullable=True),
        sa.Column("Created", sa.DateTime(), nullable=False),
        sa.Column("Updated", sa.DateTime(), nullable=False),
        sa.Column("ProcessedBy", sa.String(length=4), nullable=True),
        sa.Column("CheckedBy", sa.String(length=4), nullable=True),
        sa.Column("CONDDL (mS/cm)", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Drop the legacy daily pressure table."""
    op.drop_table("NMA_WaterLevelsContinuous_Pressure_Daily")
