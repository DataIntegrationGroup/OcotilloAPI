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
AssetAdmin view for OcotilloAPI.

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

    sortable_fields = [
        "id",
        "name",
        "mime_type",
        "storage_service",
        "size",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]

    searchable_fields = [
        "name",
        "label",
        "mime_type",
        "storage_service",
        "storage_path",
        "uri",
        "release_status",
        "created_at",
    ]

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


# ============= EOF =============================================
