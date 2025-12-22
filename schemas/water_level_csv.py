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
from pydantic import BaseModel, ConfigDict, field_validator, Field
from typing import Any

from core.enums import SampleMethod, GroundwaterLevelReason, GroundwaterLevelAccuracy


class WaterLevelCsvRow(BaseModel):
    """
    This class defines the schema for a single row in the water level CSV upload.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    well_name_point_id: str = Field(
        description="Name/PointID of the well where the measurement was taken."
    )
    field_event_date_time: datetime = Field(
        description="Date and time when the field event occurred."
    )
    field_staff: str = Field(description="Name of the person who led the field event.")
    field_staff_2: str | None = Field(
        description="Name of the second person who participated in the field event.",
        default=None,
    )
    field_staff_3: str | None = Field(
        description="Name of the third person who participated in the field event.",
        default=None,
    )
    water_level_date_time: datetime = Field(
        description="Date and time when the water level measurement was taken."
    )
    measuring_person: str = Field(
        description="Person who took the water level measurement. They must be one of the field staff"
    )
    sample_method: SampleMethod = Field(
        description="Method used to measure the water level."
    )
    mp_height: float = Field(
        description="Measuring point height relative to the ground surface in feet."
    )
    level_status: GroundwaterLevelReason = Field(
        description="Status of the water level."
    )
    depth_to_water_ft: float = Field(description="Depth to water in feet.")
    data_quality: GroundwaterLevelAccuracy = Field(
        description="A description of the accuracy of the data."
    )
    water_level_notes: str | None = Field(
        description="Additional notes about the water level measurement.", default=None
    )

    @field_validator("water_level_notes", mode="before")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("measuring_person")
    @classmethod
    def ensure_measuring_person_is_field_staff(
        cls, value: str, values: dict[str, Any]
    ) -> str:
        data = values.data
        field_staffs = [
            data.get("field_staff"),
            data.get("field_staff_2"),
            data.get("field_staff_3"),
        ]
        if value not in field_staffs:
            raise ValueError("measuring_person must be one of the field staff")
        return value


class WaterLevelBulkUploadRow(WaterLevelCsvRow):
    """
    This class extends WaterLevelCsvRow to include resolved database objects
    for easier processing during bulk upload.
    """

    well: Any = Field(description="The Thing object representing the well.")
    field_staff_contact: Any = Field(
        description="The Contact object for the field staff."
    )
    field_staff_2_contact: Any | None = Field(
        description="The Contact object for the second field staff."
    )
    field_staff_3_contact: Any | None = Field(
        description="The Contact object for the third field staff."
    )
    measuring_person_field_staff_index: int = Field(
        description="The index of the field staff who is the measuring person: 1, 2, or 3."
    )


class WaterLevelCreatedRow(BaseModel):
    """
    This class defines the structure of a successfully created water level row
    during bulk upload.
    """

    well_name_point_id: str
    field_event_id: int
    field_activity_id: int
    field_event_participant_1_id: int
    field_event_participant_2_id: int | None
    field_event_participant_3_id: int | None
    sample_id: int
    observation_id: int
    groundwater_level_reason: str
    groundwater_level_accuracy: str


class WaterLevelBulkUploadSummary(BaseModel):
    total_rows_processed: int
    total_rows_imported: int
    total_validation_errors_or_warnings: int


class WaterLevelBulkUploadPayload(BaseModel):
    summary: WaterLevelBulkUploadSummary
    water_levels: list[WaterLevelCreatedRow]
    validation_errors: list[str]


class WaterLevelBulkUploadResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    payload: WaterLevelBulkUploadPayload


# ============= EOF =============================================
