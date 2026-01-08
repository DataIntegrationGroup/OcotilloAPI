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
        CheckConstraint(
            "end_datetime > start_datetime", name="check_transuder_block_time_order"
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

    # qc_block_id: Mapped[Optional[int]] = mapped_column(
    #     ForeignKey("transducer_observation_block.id", ondelete="SET NULL"), index=True
    # )
    #
    # qc_block: Mapped[Optional["TransducerObservationBlock"]] = relationship(
    #     "TransducerObservationBlock", back_populates="observations"
    # )


# ============= EOF =============================================
