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
AssetAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Asset model.
"""
from admin.views.base import OcotilloModelView


class AssetAdmin(OcotilloModelView):
    """
    Admin view for Asset model.
    """

    # ========== Basic Configuration ==========

    name = "Assets"
    label = "Assets"
    icon = "fa fa-file"

    # ========== List View ==========

    column_list = [
        "id",
        "name",
        "label",
        "mime_type",
        "storage_service",
        "size",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "name",
        "mime_type",
        "storage_service",
        "size",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)

    search_fields = [
        "name",
        "label",
        "mime_type",
        "storage_service",
        "storage_path",
        "uri",
    ]

    column_filters = [
        "mime_type",
        "storage_service",
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
        "name",
        "label",
        "storage_service",
        "storage_path",
        "mime_type",
        "size",
        "uri",
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
        "id": "Asset ID",
        "name": "Name",
        "label": "Label",
        "storage_service": "Storage Service",
        "storage_path": "Storage Path",
        "mime_type": "MIME Type",
        "size": "Size (bytes)",
        "uri": "URI",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
