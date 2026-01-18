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

from admin.views.base import OcotilloModelView


class DeploymentAdmin(OcotilloModelView):
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

    sortable_fields = [
        "id",
        "thing_id",
        "sensor_id",
        "installation_date",
        "removal_date",
        "recording_interval",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [
        ("installation_date", True)
    ]  # True = descending (newest first)

    searchable_fields = [
        "hanging_point_description",
        "notes",
        "installation_date",
        "removal_date",
        "recording_interval_units",
        "release_status",
        "created_at",
    ]

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
