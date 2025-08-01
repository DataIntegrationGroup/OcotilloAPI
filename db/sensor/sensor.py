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
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import declared_attr, relationship

from db.base import Base, AutoBaseMixin


class SensorMixin:
    @declared_attr
    def sensor_id(self):
        return Column(
            Integer,
            ForeignKey("sensor.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )


class Sensor(Base, AutoBaseMixin):
    """
    Base class for all sensor types.
    This class can be extended to create specific sensor types.
    """

    # Define common attributes for sensors here
    name = Column(String(255), nullable=False)
    model = Column(String(50))
    serial_no = Column(String(50))
    date_installed = Column(DateTime)
    date_removed = Column(DateTime)
    recording_interval = Column(Integer)
    notes = Column(String(50))

    sample = relationship(
        "Sample",
        back_populates="sensor",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ============= EOF =============================================
