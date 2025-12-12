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
from pydantic import BaseModel


class WaterLevelBulkUploadSummary(BaseModel):
    total_rows_processed: int
    total_rows_imported: int
    validation_errors_or_warnings: int


class WaterLevelBulkUploadRow(BaseModel):
    well_name_point_id: str
    field_event_id: int
    field_activity_id: int
    sample_id: int
    observation_id: int
    measurement_date_time: str
    level_status: str
    data_quality: str


class WaterLevelBulkUploadResponse(BaseModel):
    summary: WaterLevelBulkUploadSummary
    water_levels: list[WaterLevelBulkUploadRow]
    validation_errors: list[str]


# ============= EOF =============================================
