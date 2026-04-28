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
GeologicFormationAdmin view for OcotilloAPI.
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

    sortable_fields = [
        "id",
        "formation_code",
        "lithology",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("formation_code", False)]

    searchable_fields = [
        "formation_code",
        "description",
        "lithology",
        "release_status",
        "created_at",
    ]

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


# ============= EOF =============================================
