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

from admin.views.base import OcotilloModelView


class ObservationAdmin(OcotilloModelView):
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

    sortable_fields = [
        "id",
        "observation_datetime",
        "value",
        "unit",
        "measuring_point_height",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [
        ("observation_datetime", True)
    ]  # True = descending (newest first)

    searchable_fields = [
        "groundwater_level_reason",
        "notes",
        "observation_datetime",
        "unit",
        "groundwater_level_reason",
        "release_status",
        "created_at",
    ]

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
