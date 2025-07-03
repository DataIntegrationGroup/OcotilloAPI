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

from schemas import ORMBaseModel


class CreateSpring(ORMBaseModel):
    """
    Schema for creating a spring.
    """

    location_id: int


class CreateEquipment(ORMBaseModel):
    """
    Schema for creating equipment.
    """

    location_id: int

    equipment_type: str
    model: str | None = None
    serial_no: str | None = None
    date_installed: datetime | None = None  # ISO format date string
    date_removed: datetime | None = None  # ISO format date string
    recording_interval: int | None = None  # in seconds
    equipment_notes: str | None = None


# ============= EOF =============================================
