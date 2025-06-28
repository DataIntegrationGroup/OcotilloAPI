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
from sqlalchemy import DateTime, Float, String, Integer, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declared_attr, relationship
from sqlalchemy.testing.schema import mapped_column

from db import AutoBaseMixin, Base, PropertiesMixin


class TimeseriesMixin:
    @declared_attr
    def name(self):
        return mapped_column(String(100))

    @declared_attr
    def description(self):
        return mapped_column(String(255), nullable=True)


class QCMixin:
    @declared_attr
    def quality_control_status(self):
        return mapped_column(
            String(100), ForeignKey("lexicon_term.term"), default="Provisional"
        )

    @declared_attr
    def quality_control_notes(self):
        return mapped_column(Text)

    @declared_attr
    def quality_control_timestamp(self):
        return mapped_column(DateTime, nullable=True, server_onupdate=func.now())

    @declared_attr
    def quality_control_user_id(self):
        return mapped_column(
            Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=True
        )


class WellTimeseries(Base, TimeseriesMixin, AutoBaseMixin, PropertiesMixin):
    well_id = mapped_column(
        "well_id", Integer, ForeignKey("well.id", ondelete="CASCADE"), nullable=False
    )

    equipment_id = mapped_column(
        "equipment_id",
        Integer,
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
    )


class GroundwaterLevelObservation(Base, AutoBaseMixin, PropertiesMixin, QCMixin):
    """ """

    # Define common fields for observations here
    timestamp = mapped_column(DateTime, nullable=False)
    value = mapped_column(Float, nullable=False)
    unit = mapped_column(
        String, nullable=False, default="ftbgs"
    )  # Default unit is meters

    data_quality = mapped_column(String(100), ForeignKey("lexicon_term.term"))
    level_status = mapped_column(String(100), ForeignKey("lexicon_term.term"))

    timeseries_id = mapped_column(
        "timeseries_id",
        Integer,
        ForeignKey("well_timeseries.id", ondelete="CASCADE"),
        nullable=False,
    )

    timeseries = relationship("WellTimeseries", backref="observations")

    def __repr__(self):
        return f"<Observation(id={self.id}, timestamp={self.timestamp}, value={self.value})>"


# ============= EOF =============================================
