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
LocationAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Location model.
"""
from admin.fields import CoordinateHelpField
from admin.views.base import OcotilloModelView


class LocationAdmin(OcotilloModelView):
    """
    Admin view for Location model.

    Designed to replicate MS Access "Location Entry Form" and "Location Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all locations
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published locations (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Locations"
    label = "Locations"
    icon = "fa fa-map-marker"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    sortable_fields = [
        "id",
        "description",
        "elevation",
        "county",
        "state",
        "quad_name",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]  # True = descending

    searchable_fields = [
        "description",
        "county",
        "state",
        "quad_name",
        "release_status",
        "elevation",
        "created_at",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View (MS Access Form View Equivalent) ==========

    fields = [
        "id",
        "description",
        CoordinateHelpField(
            "point",
            label="Coordinates (WKT)",
            required=True,
        ),
        "elevation",
        "county",
        "state",
        "quad_name",
        "nma_notes_location",
        "nma_coordinate_notes",
        "release_status",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_location",
        "nma_date_created",
        "nma_site_date",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_location",
        "nma_date_created",
        "nma_site_date",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_location",
        "nma_date_created",
        "nma_site_date",
    ]

    # ========== Field Labels and Help Text ==========
