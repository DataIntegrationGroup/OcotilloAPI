"""link surface water photos to surface water data

Revision ID: a1b2c3d4e5f6
Revises: f6e5d4c3b2a1
Create Date: 2026-02-05 11:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f6e5d4c3b2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_surface_water_data_surface_id",
        "NMA_SurfaceWaterData",
        ["SurfaceID"],
    )
    op.create_foreign_key(
        "fk_surface_water_photos_surface_id",
        "NMA_SurfaceWaterPhotos",
        "NMA_SurfaceWaterData",
        ["SurfaceID"],
        ["SurfaceID"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        DELETE FROM "NMA_SurfaceWaterPhotos" p
        WHERE p."SurfaceID" IS NULL
           OR NOT EXISTS (
                SELECT 1
                FROM "NMA_SurfaceWaterData" d
                WHERE d."SurfaceID" = p."SurfaceID"
           )
        """
    )
    op.alter_column(
        "NMA_SurfaceWaterPhotos",
        "SurfaceID",
        existing_type=sa.UUID(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "NMA_SurfaceWaterPhotos",
        "SurfaceID",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_constraint(
        "fk_surface_water_photos_surface_id",
        "NMA_SurfaceWaterPhotos",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_surface_water_data_surface_id",
        "NMA_SurfaceWaterData",
        type_="unique",
    )
