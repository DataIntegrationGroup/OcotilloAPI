"""Add NMA WaterLevelsContinuous_Pressure fields to transducer_observation.

Revision ID: c9f1d2e3a4b5
Revises: b7d4c6a1b2c3
Create Date: 2026-02-10 03:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c9f1d2e3a4b5"
down_revision: Union[str, Sequence[str], None] = "b7d4c6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add legacy NMA WaterLevelsContinuous_Pressure columns."""
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_checked_by",
            sa.String(length=4),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_created",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_data_source",
            sa.String(length=5),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_global_id",
            sa.String(length=40),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_measurement_method",
            sa.String(length=2),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_measuring_agency",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_notes",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_processed_by",
            sa.String(length=4),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_qced",
            sa.Boolean(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_temperature_water",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_updated",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_water_head",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_pressure_water_head_adjusted",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop legacy NMA WaterLevelsContinuous_Pressure columns."""
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_water_head_adjusted",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_water_head",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_updated",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_temperature_water",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_qced",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_processed_by",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_notes",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_measuring_agency",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_measurement_method",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_global_id",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_data_source",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_created",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_checked_by",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_pressure_conddl_ms_cm",
    )
