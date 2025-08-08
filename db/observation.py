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
from sqlalchemy import (
    ForeignKey,
    Integer,
    TIMESTAMP,
    PrimaryKeyConstraint,
    Float,
)
from sqlalchemy.orm import mapped_column, relationship

from db.base import Base, AuditMixin, ReleaseMixin, lexicon_term


class Observation(Base, AuditMixin, ReleaseMixin):
    __tablename__ = "observation"

    __versioned__ = {}

    __table_args__ = (
        PrimaryKeyConstraint(
            "id",
            "observation_timestamp",
        ),
        {},
    )

    id = mapped_column(
        Integer,
        autoincrement=True,
    )

    sample_id = mapped_column(
        Integer,
        ForeignKey("sample.id", ondelete="CASCADE"),
        nullable=False,
    )
    sensor_id = mapped_column(
        Integer,
        ForeignKey("sensor.id", ondelete="CASCADE"),
        nullable=False,
    )

    observation_timestamp = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, doc="Timestamp of the observation"
    )
    observed_property = lexicon_term()

    # groundwater
    depth_to_water = mapped_column(
        Float,
        nullable=True,
        doc="Depth to water level in ft below measuring point",
        info={"unit": "ft"},
    )

    measuring_point_height = mapped_column(
        Float,
        nullable=True,
        doc="Height of the measuring point above the ground surface in ft",
        info={"unit": "ft"},
    )

    level_status = lexicon_term()

    # geothermal
    depth = mapped_column(
        Float,
        nullable=True,
        info={"unit": "feet"},
        doc="Depth of the geothermal observation in feet",
    )
    temperature = mapped_column(
        Float,
        nullable=True,
        info={"unit": "degC"},
        doc="Temperature of the geothermal observation in degrees Celsius",
    )

    # water chemistry
    value = mapped_column(
        Float,
        nullable=True,
    )
    units = lexicon_term()

    sensor = relationship("Sensor")
    sample = relationship("Sample")


# ============= EOF =============================================
