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
NotesAdmin view for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class NotesAdmin(OcotilloModelView):
    """
    Admin view for Notes model.
    """

    # ========== Basic Configuration ==========

    name = "Notes"
    label = "Notes"
    icon = "fa fa-sticky-note"

    # ========== List View ==========

    list_fields = [
        "id",
        "target_table",
        "target_id",
        "note_type",
        "content",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    sortable_fields = [
        "id",
        "target_table",
        "target_id",
        "note_type",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]

    searchable_fields = [
        "target_table",
        "note_type",
        "content",
        "release_status",
        "created_at",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "target_table",
        "target_id",
        "note_type",
        "content",
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

    field_labels = {
        "id": "Note ID",
        "target_table": "Target Table",
        "target_id": "Target ID",
        "note_type": "Note Type",
        "content": "Content",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
