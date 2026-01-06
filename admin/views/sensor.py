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
SensorAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Sensor (Equipment) model.
"""
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import action
from starlette_admin.contrib.sqla import ModelView
from sqlalchemy import select, update

from db.sensor import Sensor


class SensorAdmin(ModelView):
    """
    Admin view for Sensor model (Equipment).

    Designed to replicate MS Access "Equipment Entry Form" and "Equipment Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all sensors
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published sensors (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Sensors"
    label = "Sensors (Equipment)"
    icon = "fa fa-microchip"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    column_list = [
        "id",
        "name",
        "sensor_type",
        "model",
        "serial_no",
        "pcn_number",
        "owner_agency",
        "sensor_status",
        "release_status",
        "created_at",
    ]

    column_sortable_list = [
        "id",
        "name",
        "sensor_type",
        "model",
        "serial_no",
        "owner_agency",
        "sensor_status",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)  # True = descending

    search_fields = [
        "name",
        "serial_no",
        "model",
        "pcn_number",
    ]

    column_filters = [
        "sensor_type",
        "owner_agency",
        "sensor_status",
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
        # Equipment Information
        "name",
        "sensor_type",
        "model",
        "serial_no",
        "pcn_number",
        "owner_agency",
        "sensor_status",
        "notes",
        # Release Status
        "release_status",
        # Audit Fields
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        # Legacy Migration Fields
        "nma_pk_equipment",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_equipment",
        # Exclude complex relationships
        "observations",
        "deployments",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_equipment",
        # Exclude complex relationships
        "observations",
        "deployments",
    ]

    # ========== Field Labels and Help Text ==========

    labels = {
        "id": "Sensor ID",
        "name": "Name",
        "sensor_type": "Type",
        "model": "Model",
        "serial_no": "Serial Number",
        "pcn_number": "PCN Number",
        "owner_agency": "Owner Agency",
        "sensor_status": "Status",
        "notes": "Notes",
        "release_status": "Release Status",
        "nma_pk_equipment": "AMPAPI Equipment ID (Legacy)",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "name": "Name or identifier for this sensor/equipment",
        "sensor_type": "Type of equipment: 'Pressure Transducer', 'Acoustic Sounder', 'Data Logger', etc.",
        "model": "Manufacturer model number",
        "serial_no": "Equipment serial number (must be unique)",
        "pcn_number": "Property Control Number for NMBGMR-owned equipment",
        "owner_agency": "Agency/organization that owns this equipment",
        "sensor_status": "Current status: 'In Service', 'In Repair', 'Retired', 'Lost', etc.",
        "notes": "General notes about this equipment",
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

    def get_list_query(self, request: Request):
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
        confirmation="Are you sure you want to publish the selected sensors?",
        submit_btn_text="Yes, publish",
        submit_btn_class="btn btn-success",
    )
    async def publish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can publish sensors", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Sensor)
                .where(Sensor.id.in_(pks))
                .values(release_status="published")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully published {updated_count} sensor(s)", status_code=200
        )

    @action(
        name="unpublish_selected",
        text="Unpublish Selected (set to draft)",
        confirmation="Are you sure you want to unpublish the selected sensors?",
        submit_btn_text="Yes, unpublish",
        submit_btn_class="btn btn-warning",
    )
    async def unpublish_selected(self, request: Request, pks: list[int]) -> Response:
        user = getattr(request.state, "user", None)
        if "admin" not in getattr(user, "roles", []):
            return Response("Only admins can unpublish sensors", status_code=403)

        from db.engine import session_ctx

        with session_ctx() as session:
            result = session.execute(
                update(Sensor).where(Sensor.id.in_(pks)).values(release_status="draft")
            )
            session.commit()
            updated_count = result.rowcount

        return Response(
            f"Successfully unpublished {updated_count} sensor(s) (set to draft)",
            status_code=200,
        )
