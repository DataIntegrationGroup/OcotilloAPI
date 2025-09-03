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

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import relationship, mapped_column, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin


class Sensor(Base, AutoBaseMixin, ReleaseMixin):
    """
    Base class for all sensor types.
    This class can be extended to create specific sensor types.
    """

    # Define common attributes for sensors here
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=True)
    serial_no: Mapped[str] = mapped_column(String(50), nullable=True)
    datetime_installed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    datetime_removed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recording_interval: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String(50), nullable=True)

    sample = relationship(
        "Sample",
        back_populates="sensor",
        cascade="all, delete-orphan",
        uselist=False,
    )


# ============= EOF =============================================
