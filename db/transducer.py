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
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import ForeignKey, Float, DateTime, Text, CheckConstraint, Index
from sqlalchemy.orm import mapped_column, Mapped, relationship

from db import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.parameter import Parameter


class TransducerObservationBlock(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a contiguous block of transducer observations that share a QC status.
    """

    parameter_id: Mapped[int] = mapped_column(
        ForeignKey("parameter.id", ondelete="CASCADE"), nullable=False, index=True
    )

    qc_status: Mapped[str] = lexicon_term()

    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    comment: Mapped[str] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str] = mapped_column(Text, nullable=True)

    # Bidirectional relationships

    parameter: Mapped["Parameter"] = relationship("Parameter")

    # Direct relationship to observations
    observations: Mapped[List["TransducerObservation"]] = relationship(
        "TransducerObservation",
        back_populates="qc_block",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "end_datetime > start_datetime", name="check_qc_block_time_order"
        ),
        Index(
            "ix_qc_block_time",
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

    qc_block_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transducer_observation_block.id", ondelete="SET NULL"), index=True
    )

    qc_block: Mapped[Optional["TransducerObservationBlock"]] = relationship(
        "TransducerObservationBlock", back_populates="observations"
    )


# ============= EOF =============================================
