# ===============================================================================
# Copyright 2026
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
AssociatedDataAdmin view for legacy NMA_AssociatedData.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_assoc_id: Legacy UUID PK (AssocID), UNIQUE for audit
- nma_location_id: Legacy LocationId UUID, UNIQUE
- nma_point_id: Legacy PointID string
- nma_object_id: Legacy OBJECTID, UNIQUE
"""

from starlette.requests import Request

from admin.views.base import OcotilloModelView


class AssociatedDataAdmin(OcotilloModelView):
    """
    Admin view for legacy AssociatedData model (NMA_AssociatedData).
    Read-only, MS Access-like listing/details.
    """

    # ========== Basic Configuration ==========
    name = "NMA Associated Data"
    label = "NMA Associated Data"
    icon = "fa fa-link"

    # Integer PK
    pk_attr = "id"
    pk_type = int

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # ========== List View ==========

    list_fields = [
        "id",
        "nma_assoc_id",
        "nma_location_id",
        "nma_point_id",
        "nma_object_id",
        "notes",
        "formation",
        "thing_id",
    ]

    sortable_fields = [
        "id",
        "nma_assoc_id",
        "nma_object_id",
        "nma_point_id",
    ]

    fields_default_sort = [("nma_point_id", False), ("nma_object_id", False)]

    searchable_fields = [
        "nma_point_id",
        "nma_assoc_id",
        "notes",
        "formation",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "nma_assoc_id",
        "nma_location_id",
        "nma_point_id",
        "nma_object_id",
        "notes",
        "formation",
        "thing_id",
    ]

    field_labels = {
        "id": "ID",
        "nma_assoc_id": "NMA AssocID (Legacy)",
        "nma_location_id": "NMA LocationId (Legacy)",
        "nma_point_id": "NMA PointID (Legacy)",
        "nma_object_id": "NMA OBJECTID (Legacy)",
        "notes": "Notes",
        "formation": "Formation",
        "thing_id": "Thing ID",
    }


# ============= EOF =============================================
