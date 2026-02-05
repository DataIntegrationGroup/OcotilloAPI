"""link weather photos to weather data

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-05 11:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_weather_data_weather_id",
        "NMA_WeatherData",
        ["WeatherID"],
    )
    op.create_foreign_key(
        "fk_weather_photos_weather_id",
        "NMA_WeatherPhotos",
        "NMA_WeatherData",
        ["WeatherID"],
        ["WeatherID"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        DELETE FROM "NMA_WeatherPhotos" p
        WHERE p."WeatherID" IS NULL
           OR NOT EXISTS (
                SELECT 1
                FROM "NMA_WeatherData" d
                WHERE d."WeatherID" = p."WeatherID"
           )
        """
    )
    op.alter_column(
        "NMA_WeatherPhotos",
        "WeatherID",
        existing_type=sa.UUID(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "NMA_WeatherPhotos",
        "WeatherID",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.drop_constraint(
        "fk_weather_photos_weather_id",
        "NMA_WeatherPhotos",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_weather_data_weather_id",
        "NMA_WeatherData",
        type_="unique",
    )
