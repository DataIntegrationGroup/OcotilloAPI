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
from admin.views.base import OcotilloModelView


class SensorAdmin(OcotilloModelView):
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

    sortable_fields = [
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

    fields_default_sort = [("created_at", True)]  # True = descending

    searchable_fields = [
        "name",
        "serial_no",
        "model",
        "pcn_number",
        "sensor_type",
        "owner_agency",
        "sensor_status",
        "release_status",
        "created_at",
    ]

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
