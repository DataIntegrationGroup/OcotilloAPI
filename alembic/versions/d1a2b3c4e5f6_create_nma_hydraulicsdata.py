"""Create legacy NMA_HydraulicsData table.

Revision ID: d1a2b3c4e5f6
Revises: c9f1d2e3a4b5
Create Date: 2026-02-10 04:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1a2b3c4e5f6"
down_revision: Union[str, Sequence[str], None] = "6e1c90f6135a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy hydraulics data table used for backfill."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_HydraulicsData"):
        op.create_table(
            "NMA_HydraulicsData",
            sa.Column(
                "GlobalID",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("WellID", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("PointID", sa.String(length=50), nullable=True),
            sa.Column("HydraulicUnit", sa.String(length=18), nullable=True),
            sa.Column(
                "thing_id",
                sa.Integer(),
                sa.ForeignKey("thing.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("TestTop", sa.SmallInteger(), nullable=False),
            sa.Column("TestBottom", sa.SmallInteger(), nullable=False),
            sa.Column("HydraulicUnitType", sa.String(length=2), nullable=True),
            sa.Column("Hydraulic Remarks", sa.String(length=200), nullable=True),
            sa.Column("T (ft2/d)", sa.Float(), nullable=True),
            sa.Column("S (dimensionless)", sa.Float(), nullable=True),
            sa.Column("Ss (ft-1)", sa.Float(), nullable=True),
            sa.Column("Sy (decimalfractn)", sa.Float(), nullable=True),
            sa.Column("KH (ft/d)", sa.Float(), nullable=True),
            sa.Column("KV (ft/d)", sa.Float(), nullable=True),
            sa.Column("HL (day-1)", sa.Float(), nullable=True),
            sa.Column("HD (ft2/d)", sa.Float(), nullable=True),
            sa.Column("Cs (gal/d/ft)", sa.Float(), nullable=True),
            sa.Column("P (decimal fraction)", sa.Float(), nullable=True),
            sa.Column("k (darcy)", sa.Float(), nullable=True),
            sa.Column("Data Source", sa.String(length=255), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_nma_hydraulicsdata_objectid",
            "NMA_HydraulicsData",
            ["OBJECTID"],
            unique=True,
        )
        op.create_index(
            "ix_nma_hydraulicsdata_pointid",
            "NMA_HydraulicsData",
            ["PointID"],
        )
        op.create_index(
            "ix_nma_hydraulicsdata_wellid",
            "NMA_HydraulicsData",
            ["WellID"],
        )


def downgrade() -> None:
    """Drop the legacy hydraulics data table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_HydraulicsData"):
        op.drop_index("ix_nma_hydraulicsdata_wellid", table_name="NMA_HydraulicsData")
        op.drop_index("ix_nma_hydraulicsdata_pointid", table_name="NMA_HydraulicsData")
        op.drop_index("ix_nma_hydraulicsdata_objectid", table_name="NMA_HydraulicsData")
        op.drop_table("NMA_HydraulicsData")
