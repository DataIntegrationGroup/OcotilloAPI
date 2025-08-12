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
from typing_extensions import Annotated

from pydantic import BaseModel, AwareDatetime, PastDatetime


# -------- CREATE ----------
class CreateSensor(BaseModel):
    """
    Schema for creating a new sensor.
    """

    name: str
    # equipment_type: str | None = None
    model: str | None = None
    serial_no: str | None = None
    datetime_installed: Annotated[AwareDatetime, PastDatetime()]
    datetime_removed: AwareDatetime | None = None  # ISO format date string
    recording_interval: int | None = None
    notes: str | None = None


# -------- RESPONSE ----------
class SensorResponse(BaseModel):
    id: int
    name: str
    model: str | None  # = Column(String(50))
    serial_no: str | None  # = Column(String(50))
    datetime_installed: AwareDatetime
    datetime_removed: AwareDatetime | None  # = Column(DateTime)
    recording_interval: int | None  # = Column(Integer)
    notes: str | None  # = Column(String(50))


# -------- UPDATE ----------
class UpdateSensor(BaseModel):
    name: str | None = None
    model: str | None = None
    serial_no: str | None = None
    datetime_installed: AwareDatetime | None = None
    datetime_removed: AwareDatetime | None = None
    recording_interval: int | None = None
    notes: str | None = None


# ============= EOF =============================================
