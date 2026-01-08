"""add surface water data legacy model

Revision ID: 1680a4a7cb77
Revises: c9f1d2e3a4b5
Create Date: 2026-01-07 20:46:51.010596

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1680a4a7cb77"
down_revision: Union[str, Sequence[str], None] = "c9f1d2e3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "NMA_SurfaceWaterData",
        sa.Column("SurfaceID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("PointID", sa.String(length=10), nullable=False),
        sa.Column("OBJECTID", sa.Integer(), primary_key=True),
        sa.Column("Discharge", sa.String(length=50), nullable=True),
        sa.Column("DischargeMethod", sa.String(length=50), nullable=True),
        sa.Column("DischargeRate", sa.Float(), nullable=True),
        sa.Column("DischargeUnits", sa.String(length=3), nullable=True),
        sa.Column("DateMeasured", sa.DateTime(), nullable=True),
        sa.Column("DischargeSource", sa.String(length=50), nullable=True),
        sa.Column("SiteNotes", sa.String(length=200), nullable=True),
        sa.Column("FieldMethodNotes", sa.String(length=200), nullable=True),
        sa.Column("FormationZone", sa.String(length=15), nullable=True),
        sa.Column("AqClass", sa.String(length=50), nullable=True),
        sa.Column("SourceNotes", sa.String(length=200), nullable=True),
        sa.Column("DataSource", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("NMA_SurfaceWaterData")
