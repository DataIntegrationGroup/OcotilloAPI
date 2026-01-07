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
GeologicFormationAdmin view for NMSampleLocations.
"""
from admin.fields import WKTField
from admin.views.base import OcotilloModelView


class GeologicFormationAdmin(OcotilloModelView):
    """
    Admin view for GeologicFormation model.
    """

    name = "Geologic Formations"
    label = "Geologic Formations"
    icon = "fa fa-layer-group"

    column_list = [
        "id",
        "formation_code",
        "lithology",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "formation_code",
        "lithology",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("formation_code", False)

    search_fields = [
        "formation_code",
        "description",
        "lithology",
    ]

    column_filters = [
        "lithology",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "id",
        "formation_code",
        "description",
        "lithology",
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

    labels = {
        "id": "Geologic Formation ID",
        "formation_code": "Formation Code",
        "description": "Description",
        "lithology": "Lithology",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
