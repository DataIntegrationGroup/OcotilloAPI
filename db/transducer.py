# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Float,
    DateTime,
    String,
    Text,
    CheckConstraint,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column, Mapped, relationship

from db import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.parameter import Parameter
    from db.contact import Contact
    from db.thing import Thing


class TransducerObservationBlock(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a contiguous block of transducer observations that share a QC status.
    Each block is associated with a specific Thing (well) to ensure uniqueness.
    """

    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"), nullable=False, index=True
    )

    parameter_id: Mapped[int] = mapped_column(
        ForeignKey("parameter.id", ondelete="CASCADE"), nullable=False, index=True
    )

    review_status: Mapped[str] = lexicon_term()

    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    comment: Mapped[str] = mapped_column(Text, nullable=True)

    # Publish provenance. A corrected block is derived data -- the numbers in it
    # are not what any instrument recorded -- so the file it came from and the
    # operations applied to it are part of the record, not metadata about it. A
    # reviewer who cannot see that a series was snapped to a manual measurement
    # cannot review it.
    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of the logger file the corrected series was derived from",
    )
    source_kind: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="What the source file measured: water_head or depth_to_water",
    )
    # A list of strings in applied order rather than a modelled correction
    # entity: the corrector's operation set is still moving, and freezing it
    # into columns now would mean a migration per new operation. The strings
    # are written by the workbench and read by humans.
    corrections: Mapped[list] = mapped_column(
        JSONB,
        nullable=True,
        comment="Corrections applied to the source series, in applied order",
    )

    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"),
        nullable=True,
        comment="Foreign key to the Contact table",
    )

    thing: Mapped["Thing"] = relationship("Thing")
    parameter: Mapped["Parameter"] = relationship("Parameter")
    reviewer: Mapped["Contact"] = relationship("Contact")

    __table_args__ = (
        UniqueConstraint(
            "thing_id",
            "review_status",
            "parameter_id",
            "start_datetime",
            "end_datetime",
            name="uq_transducer_block_thing_status_parameter_time",
        ),
        # Non-strict: a block covering a single instant is legitimate -- a
        # published file with one reading, or a block narrowed by a range
        # delete until one observation survives. The block reader matches
        # observations inclusively on both bounds, so a zero-width block still
        # covers its reading.
        CheckConstraint(
            "end_datetime >= start_datetime", name="check_transuder_block_time_order"
        ),
        Index(
            "ix_transducer_block_time",
            "start_datetime",
            "end_datetime",
        ),
    )

    # -----------------------------------------------------------------
    # Utility methods
    # -----------------------------------------------------------------
    def duration(self) -> timedelta:
        return self.end_datetime - self.start_datetime

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return not (self.end_datetime <= start or self.start_datetime >= end)


class TransducerObservation(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single observation, linked directly to its QC block.
    """

    __tablename__ = "transducer_observation"
    # Unique rather than merely indexed: without a constraint to conflict on, a
    # re-run can only avoid duplicates by deleting first, which leaves a window
    # where the data is missing. With it the loader upserts and a repeated
    # backfill is idempotent.
    #
    # Scoped to the deployment, not the thing: a deployment is a thing/sensor
    # pairing, so two sensors on one well may legitimately report the same
    # instant.
    __table_args__ = (
        UniqueConstraint(
            "deployment_id",
            "parameter_id",
            "observation_datetime",
            name="uq_transducer_observation_deployment_parameter_datetime",
        ),
    )

    parameter_id: Mapped[int] = mapped_column(
        ForeignKey("parameter.id", ondelete="CASCADE"), nullable=False, index=True
    )

    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployment.id", ondelete="CASCADE"), nullable=False
    )

    observation_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)

    # Why this reading differs from what the sensor recorded. Present only on
    # readings a correction actually moved, so a NULL note means the value is
    # as measured -- which is the distinction review needs and which the legacy
    # `nma_waterlevelscontinuous_*_notes` columns cannot carry, being scoped to
    # one legacy source each.
    note: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Per-reading correction annotation; NULL means the value is as measured",
    )

    # How far through review this reading is, on USGS terms: provisional,
    # in review, approved. Orthogonal to `release_status`, which says who may
    # see it -- a reading can be public and provisional at once, which one
    # column could not express because its lexicon lists those as siblings.
    #
    # Nullable because legacy rows predate it and nobody has established
    # whether they are approved. NULL means not stated, which is honest.
    data_maturity: Mapped[str] = lexicon_term(nullable=True)
    nma_waterlevelscontinuous_pressure_conddl_ms_cm: Mapped[float] = mapped_column(
        Float, nullable=True
    )
    nma_waterlevelscontinuous_pressure_checked_by: Mapped[str] = mapped_column(
        String(4), nullable=True
    )
    nma_waterlevelscontinuous_pressure_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nma_waterlevelscontinuous_pressure_data_source: Mapped[str] = mapped_column(
        String(5), nullable=True
    )
    nma_waterlevelscontinuous_pressure_global_id: Mapped[str] = mapped_column(
        String(40), nullable=True
    )
    nma_waterlevelscontinuous_pressure_measurement_method: Mapped[str] = mapped_column(
        String(2), nullable=True
    )
    nma_waterlevelscontinuous_pressure_measuring_agency: Mapped[str] = mapped_column(
        String(50), nullable=True
    )
    nma_waterlevelscontinuous_pressure_notes: Mapped[str] = mapped_column(
        String(100), nullable=True
    )
    nma_waterlevelscontinuous_pressure_processed_by: Mapped[str] = mapped_column(
        String(4), nullable=True
    )
    nma_waterlevelscontinuous_pressure_qced: Mapped[bool] = mapped_column(
        Boolean, nullable=True
    )
    nma_waterlevelscontinuous_pressure_temperature_water: Mapped[float] = mapped_column(
        Float, nullable=True
    )
    nma_waterlevelscontinuous_pressure_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nma_waterlevelscontinuous_pressure_water_head: Mapped[float] = mapped_column(
        Float, nullable=True
    )
    nma_waterlevelscontinuous_pressure_water_head_adjusted: Mapped[float] = (
        mapped_column(Float, nullable=True)
    )
    nma_waterlevelscontinuous_acoustic_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_data_source: Mapped[str] = mapped_column(
        String(5), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_global_id: Mapped[str] = mapped_column(
        String(40), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_measurement_method: Mapped[str] = mapped_column(
        String(2), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_measuring_agency: Mapped[str] = mapped_column(
        String(50), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_notes: Mapped[str] = mapped_column(
        String(200), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_point_id: Mapped[str] = mapped_column(
        String(50), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_pre_process_data_field: Mapped[float] = (
        mapped_column(Float, nullable=True)
    )
    nma_waterlevelscontinuous_acoustic_public_release: Mapped[bool] = mapped_column(
        Boolean, nullable=True
    )
    nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp: Mapped[float] = (
        mapped_column(Float, nullable=True)
    )
    nma_waterlevelscontinuous_acoustic_serial_no: Mapped[str] = mapped_column(
        String(50), nullable=True
    )
    nma_waterlevelscontinuous_acoustic_server_receipt_date: Mapped[datetime] = (
        mapped_column(DateTime(timezone=True), nullable=True)
    )
    nma_waterlevelscontinuous_acoustic_speaker_to_mic_length: Mapped[float] = (
        mapped_column(Float, nullable=True)
    )
    nma_waterlevelscontinuous_acoustic_temperature_air: Mapped[float] = mapped_column(
        Float, nullable=True
    )

    # qc_block_id: Mapped[Optional[int]] = mapped_column(
    #     ForeignKey("transducer_observation_block.id", ondelete="SET NULL"), index=True
    # )
    #
    # qc_block: Mapped[Optional["TransducerObservationBlock"]] = relationship(
    #     "TransducerObservationBlock", back_populates="observations"
    # )


# ============= EOF =============================================
