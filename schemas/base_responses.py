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

from schemas import ORMBaseModel


class SpringResponse(ORMBaseModel):
    """
    Response schema for spring details.
    """

    id: int
    location_id: int
    description: str | None = None


class EquipmentResponse(ORMBaseModel):
    """
    Response schema for equipment details.
    """

    id: int
    location_id: int
    equipment_type: str | None = None
    model: str | None = None
    serial_no: str | None = None
    date_installed: str | None = None  # ISO format date string
    date_removed: str | None = None  # ISO format date string
    recording_interval: int | None = None
    equipment_notes: str | None = None


# ============= EOF =============================================
