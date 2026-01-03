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
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.contrib.sqla import ModelView
from sqlalchemy import select, update

from admin.fields import CoordinateHelpField
from db.location import Location


class LocationAdmin(ModelView):
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

    column_list = [
        "id",
        "description",
        "county",
        "state",
        "elevation",
        "quad_name",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "description",
        "elevation",
        "county",
        "state",
        "quad_name",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)  # True = descending

    search_fields = [
        "description",
        "county",
        "state",
        "quad_name",
    ]

    column_filters = [
        "county",
        "state",
        "release_status",
        "elevation",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

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

    fields_default_sort = ["description", "point", "elevation", "county", "state"]

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

    labels = {
        "id": "Location ID",
        "description": "Description",
        "point": "Coordinates (WKT)",
        "elevation": "Elevation (meters)",
        "county": "County",
        "state": "State",
        "quad_name": "USGS Quad Name",
        "release_status": "Release Status",
        "nma_notes_location": "Location Notes",
        "nma_coordinate_notes": "Coordinate Notes",
        "nma_pk_location": "AMPAPI Location ID (Legacy)",
        "nma_date_created": "AMPAPI Date Created (Legacy)",
        "nma_site_date": "AMPAPI Site Date (Legacy)",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "description": "Brief description of this location (e.g., 'Well near Albuquerque')",
        "elevation": "Elevation in meters. Vertical datum: NAVD88. Will be displayed in feet in reports.",
        "release_status": "Data release status: 'draft' (internal only) or 'published' (public)",
        "nma_notes_location": "General notes about this location",
        "nma_coordinate_notes": "Notes about coordinate accuracy, source, or collection method",
        "county": "New Mexico county name",
        "state": "State (usually 'New Mexico')",
        "quad_name": "USGS 7.5-minute quadrangle map name",
    }

    # ========== Permissions (RBAC) ==========

    def can_create(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        return "admin" in getattr(user, "roles", [])

    def can_edit(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        roles = getattr(user, "roles", [])
        return "admin" in roles or "editor" in roles

    def can_delete(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        return "admin" in getattr(user, "roles", [])

    def can_view_details(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return user is not None

    # ========== Data Visibility (Release Status Filter) ==========

    async def get_list_query(self, request: Request):
        query = select(self.model)

        user = getattr(request.state, "user", None)
        if user is None:
            return query.where(self.model.id == -1)

        roles = getattr(user, "roles", [])
        if "admin" in roles or "editor" in roles:
            return query
        else:
            return query.where(self.model.release_status == "published")

    # ========== Custom Actions (MS Access "Macros" Equivalent) ==========

    @action(
        name="publish_selected",
        text="Publish Selected",
        confirmation="Are you sure you want to publish the selected locations? This will make them visible to the public.",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish locations", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Location)
                .where(Location.id.in_(pks))
                .values(release_status="published")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully published {updated_count} location(s)", status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected locations? They will no longer be visible to the public.",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish locations", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Location)
                .where(Location.id.in_(pks))
                .values(release_status="draft")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully unpublished {updated_count} location(s) (set to draft)",
            status_code=200,
        )
