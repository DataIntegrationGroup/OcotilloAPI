"""Create legacy Chemistry_SampleInfo table.

Revision ID: b7d4c6a1b2c3
Revises: 4b7aa74b15ad
Create Date: 2026-02-10 02:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "b7d4c6a1b2c3"
down_revision: Union[str, Sequence[str], None] = "5f4e2b0a6b8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy chemistry sample info table used for backfill."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_Chemistry_SampleInfo"):
        op.create_table(
            "NMA_Chemistry_SampleInfo",
            sa.Column("SamplePtID", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("WCLab_ID", sa.String(length=18), nullable=True),
            sa.Column(
                "SamplePointID", sa.String(length=10), nullable=False, unique=True
            ),
            sa.Column("AnalysesAgency", sa.String(length=50), nullable=True),
            sa.Column("StudySample", sa.Text(), nullable=True),
            sa.Column(
                "DataQuality",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("true"),
            ),
            sa.Column("SampleType", sa.String(length=50), nullable=True),
            sa.Column("CollectionDate", sa.DateTime(), nullable=True),
            sa.Column("CollectionMethod", sa.String(length=50), nullable=True),
            sa.Column("CollectedBy", sa.String(length=5), nullable=True),
            sa.Column("WaterType", sa.String(length=50), nullable=True),
            sa.Column("SampleNotes", sa.Text(), nullable=True),
            sa.Column("DataSource", sa.String(length=100), nullable=True),
            sa.Column("SampleMaterialNotH2O", sa.String(length=100), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), nullable=True, unique=True),
            sa.Column("LocationId", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "AddedDaytoDate",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "AddedMonthDaytoDate",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("false"),
            ),
            sa.Column("PublicRelease", sa.Boolean(), nullable=True),
        )


def downgrade() -> None:
    """Drop the legacy chemistry sample info table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_Chemistry_SampleInfo"):
        op.drop_table("NMA_Chemistry_SampleInfo")
