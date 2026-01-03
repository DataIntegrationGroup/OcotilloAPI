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
ThingAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Thing (Wells/Springs) model.
"""
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.contrib.sqla import ModelView
from sqlalchemy import select, update

from db.thing import Thing


class ThingAdmin(ModelView):
    """
    Admin view for Thing model (Wells, Springs, etc.).

    Designed to replicate MS Access "Well Data Entry Form" and "Well Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all things
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published things (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Things"
    label = "Things (Wells/Springs)"
    icon = "fa fa-tint"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    column_list = [
        "id",
        "name",
        "thing_type",
        "well_depth",
        "hole_depth",
        "first_visit_date",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "name",
        "thing_type",
        "well_depth",
        "hole_depth",
        "first_visit_date",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)  # True = descending

    search_fields = [
        "name",
        "thing_type",
        "well_driller_name",
    ]

    column_filters = [
        "thing_type",
        "well_depth",
        "first_visit_date",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View (MS Access Form View Equivalent) ==========

    fields = [
        "id",
        # Basic Information
        "name",
        "thing_type",
        "first_visit_date",
        # Well Construction
        "well_depth",
        "hole_depth",
        "well_casing_diameter",
        "well_casing_depth",
        "well_completion_date",
        "well_driller_name",
        "well_construction_method",
        "well_pump_type",
        "well_pump_depth",
        "formation_completion_code",
        "is_suitable_for_datalogger",
        # Spring-specific
        "spring_type",
        # Release Status
        "release_status",
        # Audit Fields
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        # Legacy Migration Fields
        "nma_pk_welldata",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_welldata",
        # Exclude complex relationships from create form
        "location_associations",
        "contact_associations",
        "asset_associations",
        "field_events",
        "deployments",
        "group_associations",
        "screens",
        "well_purposes",
        "well_casing_materials",
        "links",
        "measuring_points",
        "monitoring_frequencies",
        "aquifer_associations",
        "formation_associations",
        "status_history",
        "permission_history",
        "data_provenance",
        "notes",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_welldata",
        # Exclude complex relationships from edit form (manage separately)
        "location_associations",
        "contact_associations",
        "asset_associations",
        "field_events",
        "deployments",
        "group_associations",
        "screens",
        "well_purposes",
        "well_casing_materials",
        "links",
        "measuring_points",
        "monitoring_frequencies",
        "aquifer_associations",
        "formation_associations",
        "status_history",
        "permission_history",
        "data_provenance",
        "notes",
    ]

    # ========== Field Labels and Help Text ==========

    labels = {
        "id": "Thing ID",
        "name": "PointID",
        "thing_type": "Type",
        "first_visit_date": "First Visit Date",
        "well_depth": "Well Depth (ft)",
        "hole_depth": "Hole Depth (ft)",
        "well_casing_diameter": "Casing Diameter (in)",
        "well_casing_depth": "Casing Depth (ft)",
        "well_completion_date": "Completion Date",
        "well_driller_name": "Driller Name",
        "well_construction_method": "Construction Method",
        "well_pump_type": "Pump Type",
        "well_pump_depth": "Pump Depth (ft)",
        "formation_completion_code": "Formation Code",
        "is_suitable_for_datalogger": "Datalogger OK?",
        "spring_type": "Spring Type",
        "release_status": "Release Status",
        "nma_pk_welldata": "AMPAPI WellData ID (Legacy)",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "name": "Unique identifier for this well/spring (PointID from legacy system)",
        "thing_type": "Type of infrastructure: 'water well', 'spring', etc.",
        "first_visit_date": "Date of NMBGMR's first recorded interaction",
        "well_depth": "Total depth of well from ground surface to bottom (feet)",
        "hole_depth": "Depth of drilled hole from ground surface (feet)",
        "well_casing_diameter": "Diameter of well casing (inches)",
        "well_casing_depth": "Depth of casing from ground surface (feet)",
        "well_completion_date": "Date the well was completed",
        "well_driller_name": "Name of the well driller",
        "well_construction_method": "Method used to construct the well",
        "well_pump_type": "Type of pump installed",
        "well_pump_depth": "Depth of pump intake from ground surface (feet)",
        "formation_completion_code": "Geologic formation where well was completed",
        "is_suitable_for_datalogger": "Can a datalogger be installed at this well?",
        "spring_type": "Type of spring (for springs only)",
        "release_status": "'draft' (internal only) or 'published' (public)",
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

    # ========== Custom Actions ==========

    @action(
        name="publish_selected",
        text="Publish Selected",
        confirmation="Are you sure you want to publish the selected things? This will make them visible to the public.",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish things", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Thing)
                .where(Thing.id.in_(pks))
                .values(release_status="published")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully published {updated_count} thing(s)", status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected things? They will no longer be visible to the public.",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish things", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Thing).where(Thing.id.in_(pks)).values(release_status="draft")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully unpublished {updated_count} thing(s) (set to draft)",
            status_code=200,
        )
