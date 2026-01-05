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
DeploymentAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Deployment model.
"""
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.contrib.sqla import ModelView
from sqlalchemy import select, update

from db.deployment import Deployment


class DeploymentAdmin(ModelView):
    """
    Admin view for Deployment model (Equipment Installation Log).

    Designed to replicate MS Access "Equipment Deployment Form" and "Deployment Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all deployments
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published deployments (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Deployments"
    label = "Deployments (Equipment Installations)"
    icon = "fa fa-plug"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    column_list = [
        "id",
        "thing_id",
        "sensor_id",
        "installation_date",
        "removal_date",
        "recording_interval",
        "recording_interval_units",
        "release_status",
        "created_at",
    ]

    column_sortable_list = [
        "id",
        "thing_id",
        "sensor_id",
        "installation_date",
        "removal_date",
        "recording_interval",
        "release_status",
        "created_at",
    ]

    column_default_sort = (
        "installation_date",
        True,
    )  # True = descending (newest first)

    search_fields = [
        "hanging_point_description",
        "notes",
    ]

    column_filters = [
        "installation_date",
        "removal_date",
        "recording_interval_units",
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
        # Deployment Information
        "thing_id",
        "sensor_id",
        "installation_date",
        "removal_date",
        "recording_interval",
        "recording_interval_units",
        "hanging_cable_length",
        "hanging_point_height",
        "hanging_point_description",
        "notes",
        # Release Status
        "release_status",
        # Audit Fields
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
        # Exclude relationship objects (use IDs instead)
        "thing",
        "sensor",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        # Exclude relationship objects (use IDs instead)
        "thing",
        "sensor",
    ]

    # ========== Field Labels and Help Text ==========

    labels = {
        "id": "Deployment ID",
        "thing_id": "Well/Thing",
        "sensor_id": "Sensor/Equipment",
        "installation_date": "Installation Date",
        "removal_date": "Removal Date",
        "recording_interval": "Recording Interval",
        "recording_interval_units": "Interval Units",
        "hanging_cable_length": "Hanging Cable Length (ft)",
        "hanging_point_height": "Hanging Point Height (ft)",
        "hanging_point_description": "Hanging Point Description",
        "notes": "Notes",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "thing_id": "The well or thing where this equipment is deployed",
        "sensor_id": "The sensor/equipment being deployed",
        "installation_date": "Date the equipment was installed",
        "removal_date": "Date the equipment was removed (leave blank if still installed)",
        "recording_interval": "How often the sensor records data (numeric value)",
        "recording_interval_units": "Units for recording interval (e.g., 'minutes', 'hours')",
        "hanging_cable_length": "Length of cable from sensor to hanging point (feet)",
        "hanging_point_height": "Height of hanging point above ground (feet)",
        "hanging_point_description": "Description of the hanging point (e.g., 'Top of casing')",
        "notes": "General notes about this deployment",
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
        confirmation="Are you sure you want to publish the selected deployments?",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish deployments", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Deployment)
                .where(Deployment.id.in_(pks))
                .values(release_status="published")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully published {updated_count} deployment(s)", status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected deployments?",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish deployments", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Deployment)
                .where(Deployment.id.in_(pks))
                .values(release_status="draft")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully unpublished {updated_count} deployment(s) (set to draft)",
            status_code=200,
        )
