"""Create legacy NMA_Radionuclides table.

Revision ID: f3b4c5d6e7f8
Revises: e4f7a9c0b2d3
Create Date: 2026-03-01 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "e4f7a9c0b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy radionuclides table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_Radionuclides"):
        op.create_table(
            "NMA_Radionuclides",
            sa.Column(
                "thing_id",
                sa.Integer(),
                sa.ForeignKey("thing.id", ondelete="CASCADE"),
                nullable=False,
            ),
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
            sa.Column(
                "Uncertainty", sa.Float(), nullable=True, server_default=sa.text("0")
            ),
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
            "Radionuclides$AnalysesAgency",
            "NMA_Radionuclides",
            ["AnalysesAgency"],
        )
        op.create_index(
            "Radionuclides$Analyte",
            "NMA_Radionuclides",
            ["Analyte"],
        )
        op.create_index(
            "Radionuclides$Chemistry SampleInfoRadionuclides",
            "NMA_Radionuclides",
            ["SamplePtID"],
        )
        op.create_index(
            "Radionuclides$SamplePointID",
            "NMA_Radionuclides",
            ["SamplePointID"],
        )
        op.create_index(
            "Radionuclides$SamplePtID",
            "NMA_Radionuclides",
            ["SamplePtID"],
        )
        op.create_index(
            "Radionuclides$WCLab_ID",
            "NMA_Radionuclides",
            ["WCLab_ID"],
        )


def downgrade() -> None:
    """Drop the legacy radionuclides table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_Radionuclides"):
        op.drop_table("NMA_Radionuclides")
