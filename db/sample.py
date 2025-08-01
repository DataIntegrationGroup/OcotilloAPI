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
from sqlalchemy import DateTime, String, ForeignKey, Integer, UniqueConstraint, Float
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import mapped_column, relationship, Mapped, declared_attr

# import models from classes that are defined in separate files
from db import lexicon_term
from db.base import Base, AutoBaseMixin, ReleaseMixin
from db.thing import Thing
from db.sensor import Sensor

from typing import List, Optional

import datetime


class Sample(Base, AutoBaseMixin, ReleaseMixin):
    """
    Defines the Sample table, which stores data for individual
    sampling events.
    """

    # __table_name__ is inherited from AutoBaseMixin.

    # --- Column Definitions ---
    # Foreign Keys
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to the Thing (e.g., sampling location) table.",
    )
    sensor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sensor.id"),
        unique=True,
        comment="Foreign key for the specific equipment used.",
    )

    # Sample Attributes
    sample_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, comment="Date and time of sample collection."
    )
    sample_matrix: Mapped[Optional[str]] = mapped_column(
        comment="The material of the sample (e.g., 'gw', 'soil')."
    )
    sample_method: Mapped[Optional[str]] = mapped_column(
        comment="Method used to collect the sample."
    )
    field_sample_id: Mapped[str] = mapped_column(
        unique=True, comment="User-defined ID for field tracking."
    )
    sampler_name: Mapped[Optional[str]] = mapped_column(
        comment="Name of the person who collected the sample."
    )
    qc_sample: Mapped[str] = mapped_column(
        default="Original",
        comment="Quality control sample type (e.g., 'Original', 'field dupe').",
    )
    sample_top: Mapped[Optional[float]] = mapped_column(
        Float, comment="Top depth of a discrete sample interval."
    )
    sample_bottom: Mapped[Optional[float]] = mapped_column(
        Float, comment="Bottom depth of a discrete sample interval."
    )
    duplicate_sample_number: Mapped[int] = mapped_column(
        default=0,
        comment="Identifier for duplicate samples (0 = original sample, not a duplicate, 1 = dup no.1, 2 = dup no.2, etc.).",
    )

    # --- Relationship Definitions ---
    thing: Mapped["Thing"] = relationship(back_populates="samples")
    sensor: Mapped[Optional["Sensor"]] = relationship(back_populates="sample")

    # --- Table-level Arguments (e.g., Constraints) ---
    # Unique samples should be based on the station_id, sample_date, sample_matrix,
    # sample_top, sample_bottom, duplicate_sample, field_sample_id, and qc_sample fields.
    __table_args__ = (
        UniqueConstraint(
            "thing_id",
            "sample_date",
            "sample_matrix",
            "sample_top",
            "sample_bottom",
            "duplicate_sample_number",
            "field_sample_id",
            "qc_sample",
            name="uix_sample_uniqueness",
        ),
    )

    # ---Jake original code---
    # collection_timestamp = mapped_column(DateTime, nullable=False)
    # collection_method = lexicon_term(nullable=False)
    #
    # thing_id = mapped_column(
    #     Integer, Foreign    collection_timestamp = mapped_column(DateTime, nullable=False)
    # collection_method = lexicon_term(nullable=False)
    #
    # thing_id = mapped_column(
    #     Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    # )
    # thing = relationship("Thing")Key("thing.id", ondelete="CASCADE"), nullable=False
    # )
    # thing = relationship("Thing")

    # wells = association_proxy("author_associations", "author")


# ============= EOF =============================================
