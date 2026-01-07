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
GroupAdmin view for NMSampleLocations.
"""
from admin.fields import WKTField
from admin.views.base import OcotilloModelView


class GroupAdmin(OcotilloModelView):
    """
    Admin view for Group model.
    """

    # ========== Basic Configuration ==========

    name = "Groups"
    label = "Groups"
    icon = "fa fa-object-group"

    # ========== List View ==========

    column_list = [
        "id",
        "name",
        "group_type",
        "parent_group_id",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "name",
        "group_type",
        "parent_group_id",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("name", False)

    search_fields = [
        "name",
        "description",
    ]

    column_filters = [
        "group_type",
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
        "description",
        "group_type",
        "parent_group_id",
        WKTField("project_area", label="Project Area (WKT)"),
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
        "id": "Group ID",
        "name": "Name",
        "description": "Description",
        "group_type": "Group Type",
        "parent_group_id": "Parent Group",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
