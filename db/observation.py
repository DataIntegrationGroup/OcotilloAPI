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
from sqlalchemy import (
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import mapped_column, relationship, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term


class Observation(Base, AutoBaseMixin, ReleaseMixin):
    __versioned__ = {}

    # NM_Aquifer fields for audits
    nma_pk_waterlevel: Mapped[str] = mapped_column(nullable=True)

    sample_id: Mapped[int] = mapped_column(
        ForeignKey("sample.id", ondelete="CASCADE"),
        nullable=False,
    )
    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensor.id", ondelete="CASCADE"),
        nullable=True,
    )

    observation_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, doc="Timestamp of the observation"
    )
    observed_property: Mapped[str] = lexicon_term(nullable=False)
    value: Mapped[float] = mapped_column(
        nullable=True,
    )
    unit: Mapped[str] = lexicon_term(nullable=False)

    # groundwater
    measuring_point_height: Mapped[float] = mapped_column(
        nullable=True,
        doc="Height of the measuring point above the ground surface in ft",
        info={"unit": "ft"},
    )

    level_status: Mapped[str] = lexicon_term(nullable=True)

    # geothermal
    observation_depth: Mapped[float] = mapped_column(
        nullable=True,
        info={"unit": "feet"},
        doc="Depth of the geothermal observation in feet",
    )

    sensor: Mapped["Sensor"] = relationship("Sensor")  # noqa: F821
    sample: Mapped["Sample"] = relationship("Sample")  # noqa: F821


# ============= EOF =============================================
