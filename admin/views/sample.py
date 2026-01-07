# ===============================================================================
# Copyright 2025
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
SampleAdmin view for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class SampleAdmin(OcotilloModelView):
    """
    Admin view for Sample model.
    """

    # ========== Basic Configuration ==========

    name = "Samples"
    label = "Samples"
    icon = "fa fa-flask"

    # ========== List View ==========

    column_list = [
        "id",
        "sample_name",
        "sample_date",
        "sample_matrix",
        "sample_method",
        "qc_type",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "sample_name",
        "sample_date",
        "sample_matrix",
        "sample_method",
        "qc_type",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("sample_date", True)

    search_fields = [
        "sample_name",
        "notes",
        "nma_pk_waterlevels",
    ]

    column_filters = [
        "sample_matrix",
        "sample_method",
        "qc_type",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "field_activity_id",
        "field_event_participant_id",
        "sample_date",
        "sample_name",
        "sample_matrix",
        "sample_method",
        "qc_type",
        "depth_top",
        "depth_bottom",
        "notes",
        "nma_pk_waterlevels",
        "release_status",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
    ]

    labels = {
        "id": "Sample ID",
        "field_activity_id": "Field Activity",
        "field_event_participant_id": "Field Event Participant",
        "sample_date": "Sample Date",
        "sample_name": "Sample Name",
        "sample_matrix": "Sample Matrix",
        "sample_method": "Sample Method",
        "qc_type": "QC Type",
        "depth_top": "Depth Top (ft)",
        "depth_bottom": "Depth Bottom (ft)",
        "notes": "Notes",
        "nma_pk_waterlevels": "AMPAPI WaterLevels ID (Legacy)",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
