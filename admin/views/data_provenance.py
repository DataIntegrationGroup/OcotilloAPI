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
DataProvenanceAdmin view for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class DataProvenanceAdmin(OcotilloModelView):
    """
    Admin view for DataProvenance model.
    """

    name = "Data Provenance"
    label = "Data Provenance"
    icon = "fa fa-history"

    column_list = [
        "id",
        "target_table",
        "target_id",
        "field_name",
        "origin_type",
        "origin_source",
        "collection_method",
        "accuracy_value",
        "accuracy_unit",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "target_table",
        "target_id",
        "field_name",
        "origin_type",
        "collection_method",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)

    search_fields = [
        "target_table",
        "field_name",
        "origin_source",
    ]

    column_filters = [
        "target_table",
        "origin_type",
        "collection_method",
        "accuracy_unit",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "id",
        "target_table",
        "target_id",
        "field_name",
        "origin_type",
        "origin_source",
        "collection_method",
        "accuracy_value",
        "accuracy_unit",
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
        "id": "Provenance ID",
        "target_table": "Target Table",
        "target_id": "Target ID",
        "field_name": "Field Name",
        "origin_type": "Origin Type",
        "origin_source": "Origin Source",
        "collection_method": "Collection Method",
        "accuracy_value": "Accuracy Value",
        "accuracy_unit": "Accuracy Unit",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
