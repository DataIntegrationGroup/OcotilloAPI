# ===============================================================================
# Copyright 2026
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
"""
WaterLevelsContinuousPressureDailyAdmin view for legacy NMA_WaterLevelsContinuous_Pressure_Daily.
"""
from starlette.requests import Request

from admin.views.base import OcotilloModelView


class WaterLevelsContinuousPressureDailyAdmin(OcotilloModelView):
    """
    Admin view for NMA_WaterLevelsContinuous_Pressure_Daily model.
    """

    # ========== Basic Configuration ==========
    name = "NMA Water Levels Continuous Pressure Daily"
    label = "NMA Water Levels Continuous Pressure Daily"
    icon = "fa fa-tachometer-alt"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # ========== List View ==========
    list_fields = [
        "global_id",
        "object_id",
        "well_id",
        "point_id",
        "date_measured",
        "temperature_water",
        "water_head",
        "water_head_adjusted",
        "depth_to_water_bgs",
        "measurement_method",
        "data_source",
        "measuring_agency",
        "qced",
        "notes",
        "created",
        "updated",
        "processed_by",
        "checked_by",
        "cond_dl_ms_cm",
    ]

    sortable_fields = [
        "global_id",
        "object_id",
        "well_id",
        "point_id",
        "date_measured",
        "water_head",
        "depth_to_water_bgs",
        "measurement_method",
        "data_source",
        "measuring_agency",
        "qced",
        "created",
        "updated",
        "processed_by",
        "checked_by",
        "cond_dl_ms_cm",
    ]

    fields_default_sort = [("date_measured", True)]

    searchable_fields = [
        "global_id",
        "well_id",
        "point_id",
        "date_measured",
        "measurement_method",
        "data_source",
        "measuring_agency",
        "notes",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Detail View ==========
    fields = [
        "global_id",
        "object_id",
        "well_id",
        "point_id",
        "date_measured",
        "temperature_water",
        "water_head",
        "water_head_adjusted",
        "depth_to_water_bgs",
        "measurement_method",
        "data_source",
        "measuring_agency",
        "qced",
        "notes",
        "created",
        "updated",
        "processed_by",
        "checked_by",
        "cond_dl_ms_cm",
    ]

    field_labels = {
        "global_id": "GlobalID",
        "object_id": "OBJECTID",
        "well_id": "WellID",
        "point_id": "PointID",
        "date_measured": "Date Measured",
        "temperature_water": "Temperature Water",
        "water_head": "Water Head",
        "water_head_adjusted": "Water Head Adjusted",
        "depth_to_water_bgs": "Depth To Water (BGS)",
        "measurement_method": "Measurement Method",
        "data_source": "Data Source",
        "measuring_agency": "Measuring Agency",
        "qced": "QCed",
        "notes": "Notes",
        "created": "Created",
        "updated": "Updated",
        "processed_by": "Processed By",
        "checked_by": "Checked By",
        "cond_dl_ms_cm": "CONDDL (mS/cm)",
    }


# ============= EOF =============================================
