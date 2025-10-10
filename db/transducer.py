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
from sqlalchemy import Integer, ForeignKey, Float, DateTime
from sqlalchemy.orm import mapped_column, Mapped

from db import Base, AutoBaseMixin, ReleaseMixin


class TransducerObservation(Base, AutoBaseMixin, ReleaseMixin):
    __tablename__ = "transducer_observations"

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE")
    )
    transducer_id = mapped_column(Integer, ForeignKey("sensor.id"))
    value = mapped_column(Float, nullable=False)
    observation_datetime = mapped_column(DateTime(timezone=True), nullable=False)
    parameter_id = mapped_column(Integer, ForeignKey("parameter.id"))


# ============= EOF =============================================
