"""add acoustic legacy fields to transducer observations

Revision ID: 8ed4b9770721
Revises: 1680a4a7cb77
Create Date: 2026-01-07 22:12:20.045062

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8ed4b9770721"
down_revision: Union[str, Sequence[str], None] = "1680a4a7cb77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_created",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_data_source",
            sa.String(length=5),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_global_id",
            sa.String(length=40),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_measurement_method",
            sa.String(length=2),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_measuring_agency",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_notes",
            sa.String(length=200),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_point_id",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_public_release",
            sa.Boolean(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_serial_no",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_server_receipt_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "transducer_observation",
        sa.Column(
            "nma_waterlevelscontinuous_acoustic_temperature_air",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_temperature_air",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_server_receipt_date",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_serial_no",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_public_release",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_pre_process_data_field",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_point_id",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_notes",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_measuring_agency",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_measurement_method",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_global_id",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_data_source",
    )
    op.drop_column(
        "transducer_observation",
        "nma_waterlevelscontinuous_acoustic_created",
    )
