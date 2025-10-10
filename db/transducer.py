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

from sqlalchemy import Integer, ForeignKey, Float, DateTime
from sqlalchemy.orm import mapped_column, Mapped, relationship

from db import Base, AutoBaseMixin, ReleaseMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.thing import Thing
    from db.parameter import Parameter


class TransducerObservation(Base, AutoBaseMixin, ReleaseMixin):
    __tablename__ = "transducer_observations"

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE")
    )
    # sensor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sensor.id"))
    parameter_id: Mapped[int] = mapped_column(Integer, ForeignKey("parameter.id"))

    value: Mapped[float] = mapped_column(Float)
    observation_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    thing: Mapped["Thing"] = relationship("Thing")
    # sensor: Mapped["Sensor"] = relationship("Sensor")
    parameter: Mapped["Parameter"] = relationship("Parameter")


# ============= EOF =============================================
