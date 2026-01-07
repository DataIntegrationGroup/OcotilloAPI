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
AquiferTypeAdmin view for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class AquiferTypeAdmin(OcotilloModelView):
    """
    Admin view for AquiferType model.
    """

    # ========== Basic Configuration ==========

    name = "Aquifer Types"
    label = "Aquifer Types"
    icon = "fa fa-tint"

    # ========== List View ==========

    column_list = [
        "id",
        "thing_aquifer_association_id",
        "aquifer_type",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "thing_aquifer_association_id",
        "aquifer_type",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)

    search_fields = [
        "aquifer_type",
    ]

    column_filters = [
        "aquifer_type",
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
        "thing_aquifer_association_id",
        "aquifer_type",
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
        "id": "Aquifer Type ID",
        "thing_aquifer_association_id": "Thing-Aquifer Association",
        "aquifer_type": "Aquifer Type",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
