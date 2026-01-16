"""Create legacy NMA_WeatherPhotos table.

Revision ID: e4b5c6d7e8f9
Revises: d3a4b5c6d7e8
Create Date: 2026-03-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "d3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the legacy weather photos table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_WeatherPhotos"):
        op.create_table(
            "NMA_WeatherPhotos",
            sa.Column("WeatherID", postgresql.UUID(as_uuid=True), nullable=True),
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
        op.create_index("WeatherPhotos$PointID", "NMA_WeatherPhotos", ["PointID"])
        op.create_index("WeatherPhotos$WeatherID", "NMA_WeatherPhotos", ["WeatherID"])


def downgrade() -> None:
    """Drop the legacy weather photos table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("NMA_WeatherPhotos"):
        op.drop_table("NMA_WeatherPhotos")
