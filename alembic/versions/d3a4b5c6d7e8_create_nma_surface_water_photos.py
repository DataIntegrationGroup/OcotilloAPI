"""Create legacy NMA_SurfaceWaterPhotos table.

Revision ID: d3a4b5c6d7e8
Revises: c2f4a9d0b1e2
Create Date: 2026-03-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "c2f4a9d0b1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy surface water photos table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_SurfaceWaterPhotos"):
        op.create_table(
            "NMA_SurfaceWaterPhotos",
            sa.Column("SurfaceID", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("PointID", sa.String(length=50), nullable=False),
            sa.Column("OLEPath", sa.String(length=50), nullable=True),
            sa.Column("OBJECTID", sa.Integer(), nullable=True, unique=True),
            sa.Column(
                "GlobalID",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                primary_key=True,
            ),
        )
        op.create_index(
            "SurfaceWaterPhotos$PointID", "NMA_SurfaceWaterPhotos", ["PointID"]
        )
        op.create_index(
            "SurfaceWaterPhotos$SurfaceID", "NMA_SurfaceWaterPhotos", ["SurfaceID"]
        )


def downgrade() -> None:
    """Drop the legacy surface water photos table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_SurfaceWaterPhotos"):
        op.drop_table("NMA_SurfaceWaterPhotos")
