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
ObservationAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Observation (Water Levels) model.
"""
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.contrib.sqla import ModelView
from sqlalchemy import select, update

from db.observation import Observation


class ObservationAdmin(ModelView):
    """
    Admin view for Observation model (Water Levels).

    Designed to replicate MS Access "Water Level Entry Form" and "Water Level Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all observations
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published observations (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Observations"
    label = "Observations (Water Levels)"
    icon = "fa fa-line-chart"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    column_list = [
        "id",
        "observation_datetime",
        "value",
        "unit",
        "measuring_point_height",
        "groundwater_level_reason",
        "release_status",
        "created_at",
    ]

    column_sortable_list = [
        "id",
        "observation_datetime",
        "value",
        "unit",
        "measuring_point_height",
        "release_status",
        "created_at",
    ]

    column_default_sort = (
        "observation_datetime",
        True,
    )  # True = descending (newest first)

    search_fields = [
        "groundwater_level_reason",
        "notes",
    ]

    column_filters = [
        "observation_datetime",
        "unit",
        "groundwater_level_reason",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200, 500]

    # ========== Form View (MS Access Form View Equivalent) ==========

    fields = [
        "id",
        # Core measurement data
        "observation_datetime",
        "value",
        "unit",
        "measuring_point_height",
        "groundwater_level_reason",
        "notes",
        # Relationships (display as selects)
        "sample_id",
        "sensor_id",
        "parameter_id",
        "analysis_method_id",
        # Release Status
        "release_status",
        # Audit Fields
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        # Legacy Migration Fields
        "nma_pk_waterlevels",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_waterlevels",
        # Exclude relationship objects (use IDs instead)
        "sample",
        "sensor",
        "parameter",
        "analysis_method",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_waterlevels",
        # Exclude relationship objects (use IDs instead)
        "sample",
        "sensor",
        "parameter",
        "analysis_method",
    ]

    # ========== Field Labels and Help Text ==========

    labels = {
        "id": "Observation ID",
        "observation_datetime": "Date/Time Measured",
        "value": "Depth to Water (ft)",
        "unit": "Unit",
        "measuring_point_height": "MP Height (ft)",
        "groundwater_level_reason": "Level Status/Reason",
        "notes": "Notes",
        "sample_id": "Sample",
        "sensor_id": "Sensor/Equipment",
        "parameter_id": "Parameter",
        "analysis_method_id": "Analysis Method",
        "release_status": "Release Status",
        "nma_pk_waterlevels": "AMPAPI WaterLevels ID (Legacy)",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "observation_datetime": "Date and time of the water level measurement (UTC)",
        "value": "Depth to water from measuring point (feet)",
        "unit": "Unit of measurement (typically 'ft' for feet)",
        "measuring_point_height": "Height of measuring point above ground surface (feet)",
        "groundwater_level_reason": "Reason/status: obstruction, dry well, equipment failure, etc. Leave blank if normal measurement.",
        "notes": "Additional notes about this observation",
        "sample_id": "Associated sample record",
        "sensor_id": "Equipment used to take measurement (if automated)",
        "parameter_id": "The parameter being measured (e.g., 'Depth to Water')",
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
        confirmation="Are you sure you want to publish the selected observations? This will make them visible to the public.",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish observations", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Observation)
                .where(Observation.id.in_(pks))
                .values(release_status="published")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully published {updated_count} observation(s)", status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected observations? They will no longer be visible to the public.",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish observations", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Observation)
                .where(Observation.id.in_(pks))
                .values(release_status="draft")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully unpublished {updated_count} observation(s) (set to draft)",
            status_code=200,
        )
