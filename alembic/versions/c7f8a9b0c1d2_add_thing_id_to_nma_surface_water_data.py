"""add thing_id to NMA_SurfaceWaterData

Revision ID: c7f8a9b0c1d2
Revises: 71a4c6b3d2e8
Create Date: 2026-02-04 12:03:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "71a4c6b3d2e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "NMA_SurfaceWaterData",
        sa.Column("thing_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_surface_water_data_thing_id",
        "NMA_SurfaceWaterData",
        "thing",
        ["thing_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Backfill thing_id based on LocationId -> Thing.nma_pk_location
    op.execute(
        """
        UPDATE "NMA_SurfaceWaterData" sw
        SET thing_id = t.id
        FROM thing t
        WHERE t.nma_pk_location IS NOT NULL
          AND sw."LocationId" IS NOT NULL
          AND t.nma_pk_location = sw."LocationId"::text
        """
    )
    # Remove any rows that cannot be linked to a Thing, then enforce NOT NULL
    op.execute('DELETE FROM "NMA_SurfaceWaterData" WHERE thing_id IS NULL')
    op.alter_column(
        "NMA_SurfaceWaterData", "thing_id", existing_type=sa.Integer(), nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_surface_water_data_thing_id",
        "NMA_SurfaceWaterData",
        type_="foreignkey",
    )
    op.drop_column("NMA_SurfaceWaterData", "thing_id")
