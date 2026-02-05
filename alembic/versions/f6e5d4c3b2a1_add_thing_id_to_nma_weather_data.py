"""add thing_id to NMA_WeatherData

Revision ID: f6e5d4c3b2a1
Revises: c7f8a9b0c1d2
Create Date: 2026-02-05 10:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e5d4c3b2a1"
down_revision: Union[str, Sequence[str], None] = "c7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "NMA_WeatherData",
        sa.Column("thing_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_weather_data_thing_id",
        "NMA_WeatherData",
        "thing",
        ["thing_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Backfill thing_id based on LocationId -> Thing.nma_pk_location
    op.execute(
        """
        UPDATE "NMA_WeatherData" wd
        SET thing_id = t.id
        FROM thing t
        WHERE t.nma_pk_location IS NOT NULL
          AND wd."LocationId" IS NOT NULL
          AND t.nma_pk_location = wd."LocationId"::text
        """
    )
    # Remove any rows that cannot be linked to a Thing, then enforce NOT NULL
    op.execute('DELETE FROM "NMA_WeatherData" WHERE thing_id IS NULL')
    op.alter_column(
        "NMA_WeatherData", "thing_id", existing_type=sa.Integer(), nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_weather_data_thing_id",
        "NMA_WeatherData",
        type_="foreignkey",
    )
    op.drop_column("NMA_WeatherData", "thing_id")
