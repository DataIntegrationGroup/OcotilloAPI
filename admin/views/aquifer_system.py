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
AquiferSystemAdmin view for NMSampleLocations.
"""
from admin.fields import WKTField
from admin.views.base import OcotilloModelView


class AquiferSystemAdmin(OcotilloModelView):
    """
    Admin view for AquiferSystem model.
    """

    # ========== Basic Configuration ==========

    name = "Aquifer Systems"
    label = "Aquifer Systems"
    icon = "fa fa-globe"

    # ========== List View ==========

    list_fields = [
        "id",
        "name",
        "primary_aquifer_type",
        "geographic_scale",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    sortable_fields = [
        "id",
        "name",
        "primary_aquifer_type",
        "geographic_scale",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("name", False)]

    searchable_fields = [
        "name",
        "description",
        "primary_aquifer_type",
        "geographic_scale",
        "release_status",
        "created_at",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "name",
        "description",
        "primary_aquifer_type",
        "geographic_scale",
        WKTField("boundary", label="Boundary (WKT)"),
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
        "id": "Aquifer System ID",
        "name": "Name",
        "description": "Description",
        "primary_aquifer_type": "Primary Aquifer Type",
        "geographic_scale": "Geographic Scale",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
