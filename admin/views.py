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
Admin views for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on database models.

For MS Access users: This interface provides familiar functionality:
    - List View = MS Access Datasheet View (grid of records with sorting/filtering)
    - Create/Edit Forms = MS Access Form View (enter/edit data)
    - Search = MS Access "Find" feature (Ctrl+F)
    - Filters = MS Access "Filter by Selection"
    - Export = MS Access "Export to Excel"
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

    model = Location
    name = "Locations"
    label = "Locations"
    icon = "fa fa-map-marker"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    # Columns to display in list view (table grid)
    # Ordered by importance/frequency of use (mimicking Access datasheet)
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

    # Columns that can be sorted (like clicking column headers in Access)
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

    # Default sort (newest first)
    column_default_sort = ("created_at", True)  # True = descending

    # Searchable fields (like MS Access "Find" feature - Ctrl+F)
    search_fields = [
        "description",
        "county",
        "state",
        "quad_name",
    ]

    # Filterable columns (like MS Access "Filter" dropdown)
    column_filters = [
        "county",
        "state",
        "release_status",
        "elevation",
        "created_at",
    ]

    # Enable export (like MS Access "Export to Excel")
    can_export = True
    export_types = ["csv", "excel"]

    # Number of rows per page (like MS Access datasheet pagination)
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View (MS Access Form View Equivalent) ==========

    # Fields to display in create/edit form
    # Grouped logically like MS Access form sections
    fields = [
        # Basic Information Section
        "description",

        # Geographic Information Section
        CoordinateHelpField(
            "point",
            label="Coordinates (WKT)",
            required=True,
        ),
        "elevation",
        "county",
        "state",
        "quad_name",

        # Notes Section
        "nma_notes_location",
        "nma_coordinate_notes",

        # Release Status
        "release_status",
    ]

    # Fields to show in detail view (read-only display)
    fields_default_sort = ["description", "point", "elevation", "county", "state"]

    # Fields excluded from create form (auto-populated or computed)
    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_location",  # Only populated during migration from AMPAPI
        "nma_date_created",  # Only populated during migration
        "nma_site_date",  # Only populated during migration
    ]

    # Fields excluded from edit form
    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_location",  # Migration-only, read-only
        "nma_date_created",  # Migration-only, read-only
        "nma_site_date",  # Migration-only, read-only
    ]

    # ========== Field Labels and Help Text ==========

    # Field display customization (MS Access form labels)
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

    # Field help text (tooltips - like Access field descriptions)
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
        """
        Only admins can create new locations.

        Returns:
            bool: True if user has 'admin' role
        """
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        return "admin" in getattr(user, "roles", [])

    def can_edit(self, request: Request) -> bool:
        """
        Admins and editors can edit locations.

        Returns:
            bool: True if user has 'admin' or 'editor' role
        """
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        roles = getattr(user, "roles", [])
        return "admin" in roles or "editor" in roles

    def can_delete(self, request: Request) -> bool:
        """
        Only admins can delete locations.

        Deletion is a high-impact operation that should be restricted.

        Returns:
            bool: True if user has 'admin' role
        """
        user = getattr(request.state, "user", None)
        if user is None:
            return False
        return "admin" in getattr(user, "roles", [])

    def can_view_details(self, request: Request) -> bool:
        """
        All authenticated users can view location details.

        Returns:
            bool: True if user is authenticated
        """
        user = getattr(request.state, "user", None)
        return user is not None

    # ========== Data Visibility (Release Status Filter) ==========

    async def get_list_query(self, request: Request):
        """
        Override list query to filter by release_status based on user role.

        Access control:
            - Admin/Editor: See all records (draft + published)
            - Viewer: See only published records
            - Anonymous: No access (redirected to login)

        This replicates MS Access security where certain users could only see
        specific records based on field values.

        Returns:
            SQLAlchemy select query with appropriate filters
        """
        query = select(self.model)

        user = getattr(request.state, "user", None)
        if user is None:
            # No access for anonymous users (should be redirected to login)
            return query.where(self.model.id == -1)  # Return empty set

        roles = getattr(user, "roles", [])
        if "admin" in roles or "editor" in roles:
            # Admins and editors see all records
            return query
        else:
            # Viewers only see published records
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
        """
        Bulk action to publish selected locations.

        Similar to MS Access "Update Query" or VBA macro that changes field values
        for multiple records at once.

        This changes release_status from 'draft' to 'published' for selected locations.

        Args:
            request: Starlette request object
            pks: List of primary keys (location IDs) to publish

        Returns:
            Response with success message
        """
        # Check permissions - only admins can publish
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish locations", status_code=403)

        # Update records
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
            f"Successfully published {updated_count} location(s)",
            status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected locations? They will no longer be visible to the public.",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        """
        Bulk action to unpublish selected locations (set to draft).

        Args:
            request: Starlette request object
            pks: List of primary keys (location IDs) to unpublish

        Returns:
            Response with success message
        """
        # Check permissions - only admins can unpublish
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish locations", status_code=403)

        # Update records
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
            status_code=200
        )

    # TODO: Future bulk actions
    # - Export as GeoJSON
    # - Export as Shapefile
    # - Bulk coordinate conversion (UTM ’ WGS84)
    # - Validate coordinates (check if in New Mexico)
