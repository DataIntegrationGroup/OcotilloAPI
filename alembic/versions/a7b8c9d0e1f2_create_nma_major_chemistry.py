"""Create legacy NMA_MajorChemistry table.

Revision ID: a7b8c9d0e1f2
Revises: f3b4c5d6e7f8
Create Date: 2026-03-01 02:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy major chemistry table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_MajorChemistry"):
        op.create_table(
            "NMA_MajorChemistry",
            sa.Column(
                "SamplePtID",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(
                    "NMA_Chemistry_SampleInfo.SamplePtID", ondelete="CASCADE"
                ),
                nullable=False,
            ),
            sa.Column("SamplePointID", sa.String(length=10), nullable=True),
            sa.Column("Analyte", sa.String(length=50), nullable=True),
            sa.Column("Symbol", sa.String(length=50), nullable=True),
            sa.Column(
                "SampleValue", sa.Float(), nullable=True, server_default=sa.text("0")
            ),
            sa.Column("Units", sa.String(length=50), nullable=True),
            sa.Column("Uncertainty", sa.Float(), nullable=True),
            sa.Column("AnalysisMethod", sa.String(length=255), nullable=True),
            sa.Column("AnalysisDate", sa.DateTime(), nullable=True),
            sa.Column("Notes", sa.String(length=255), nullable=True),
            sa.Column(
                "Volume", sa.Integer(), nullable=True, server_default=sa.text("0")
            ),
            sa.Column("VolumeUnit", sa.String(length=50), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), nullable=True, unique=True),
            sa.Column(
                "GlobalID",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                primary_key=True,
            ),
            sa.Column("AnalysesAgency", sa.String(length=50), nullable=True),
            sa.Column("WCLab_ID", sa.String(length=25), nullable=True),
        )
        op.create_index(
            "MajorChemistry$AnalysesAgency",
            "NMA_MajorChemistry",
            ["AnalysesAgency"],
        )
        op.create_index(
            "MajorChemistry$Analyte",
            "NMA_MajorChemistry",
            ["Analyte"],
        )
        op.create_index(
            "MajorChemistry$Chemistry SampleInfoMajorChemistry",
            "NMA_MajorChemistry",
            ["SamplePtID"],
        )
        op.create_index(
            "MajorChemistry$SamplePointID",
            "NMA_MajorChemistry",
            ["SamplePointID"],
        )
        op.create_index(
            "MajorChemistry$SamplePointIDAnalyte",
            "NMA_MajorChemistry",
            ["SamplePointID", "Analyte"],
        )
        op.create_index(
            "MajorChemistry$SamplePtID",
            "NMA_MajorChemistry",
            ["SamplePtID"],
        )
        op.create_index(
            "MajorChemistry$WCLab_ID",
            "NMA_MajorChemistry",
            ["WCLab_ID"],
        )


def downgrade() -> None:
    """Drop the legacy major chemistry table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_MajorChemistry"):
        op.drop_table("NMA_MajorChemistry")
