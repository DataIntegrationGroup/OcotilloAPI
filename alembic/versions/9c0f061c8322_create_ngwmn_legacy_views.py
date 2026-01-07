"""Create legacy NGWMN view tables

Revision ID: 9c0f061c8322
Revises: 7c02d9f8f412
Create Date: 2026-02-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "9c0f061c8322"
down_revision: Union[str, Sequence[str], None] = "7c02d9f8f412"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the three NGWMN legacy view tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("NMA_view_NGWMN_WellConstruction"):
        op.create_table(
            "NMA_view_NGWMN_WellConstruction",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("PointID", sa.String(length=50), nullable=True),
            sa.Column("CasingTop", sa.Float(), nullable=True),
            sa.Column("CasingBottom", sa.Float(), nullable=True),
            sa.Column("CasingDepthUnits", sa.String(length=20), nullable=True),
            sa.Column("ScreenTop", sa.Float(), nullable=True),
            sa.Column("ScreenBottom", sa.Float(), nullable=True),
            sa.Column("ScreenBottomUnit", sa.String(length=20), nullable=True),
            sa.Column("ScreenDescription", sa.String(length=250), nullable=True),
            sa.Column("CasingDescription", sa.String(length=250), nullable=True),
        )

    if not inspector.has_table("NMA_view_NGWMN_WaterLevels"):
        op.create_table(
            "NMA_view_NGWMN_WaterLevels",
            sa.Column("PointID", sa.String(length=50), primary_key=True),
            sa.Column("DateMeasured", sa.Date(), primary_key=True),
            sa.Column("DepthToWaterBGS", sa.Float(), nullable=True),
            sa.Column("WLUnits", sa.String(length=10), nullable=True),
            sa.Column("MeasurementMethod", sa.String(length=50), nullable=True),
            sa.Column("WLAccuracy", sa.Float(), nullable=True),
            sa.Column("PublicRelease", sa.Boolean(), nullable=True),
        )

    if not inspector.has_table("NMA_view_NGWMN_Lithology"):
        op.create_table(
            "NMA_view_NGWMN_Lithology",
            sa.Column("OBJECTID", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("PointID", sa.String(length=50), nullable=True),
            sa.Column("Lithology", sa.String(length=50), nullable=True),
            sa.Column("TERM", sa.String(length=100), nullable=True),
            sa.Column("StratSource", sa.String(length=100), nullable=True),
            sa.Column("StratTop", sa.Float(), nullable=True),
            sa.Column("StratTopUnit", sa.String(length=20), nullable=True),
            sa.Column("StratBottom", sa.Float(), nullable=True),
            sa.Column("StratBottomUnit", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    """Drop the NGWMN legacy view tables."""
    bind = op.get_bind()
    inspector = inspect(bind)

    for table in (
        "NMA_view_NGWMN_Lithology",
        "NMA_view_NGWMN_WaterLevels",
        "NMA_view_NGWMN_WellConstruction",
    ):
        if inspector.has_table(table):
            op.drop_table(table)
