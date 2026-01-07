"""Add unique constraints for NGWMN backfill upserts

Revision ID: 8a1de3e3f0b3
Revises: 9c0f061c8322
Create Date: 2026-02-10 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8a1de3e3f0b3"
down_revision: Union[str, Sequence[str], None] = "9c0f061c8322"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraints to support ON CONFLICT upserts."""
    op.create_unique_constraint(
        "uq_nma_view_ngwmn_waterlevels_point_date",
        "NMA_view_NGWMN_WaterLevels",
        ["PointID", "DateMeasured"],
    )
    op.create_unique_constraint(
        "uq_nma_view_ngwmn_wellconstruction_point_casing_screen",
        "NMA_view_NGWMN_WellConstruction",
        ["PointID", "CasingTop", "ScreenTop"],
    )
    op.create_unique_constraint(
        "uq_nma_view_ngwmn_lithology_objectid",
        "NMA_view_NGWMN_Lithology",
        ["OBJECTID"],
    )


def downgrade() -> None:
    """Drop unique constraints."""
    op.drop_constraint(
        "uq_nma_view_ngwmn_lithology_objectid",
        "NMA_view_NGWMN_Lithology",
        type_="unique",
    )
    op.drop_constraint(
        "uq_nma_view_ngwmn_wellconstruction_point_casing_screen",
        "NMA_view_NGWMN_WellConstruction",
        type_="unique",
    )
    op.drop_constraint(
        "uq_nma_view_ngwmn_waterlevels_point_date",
        "NMA_view_NGWMN_WaterLevels",
        type_="unique",
    )
