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

from admin.views.base import OcotilloModelView


class ThingAdmin(OcotilloModelView):
    """
    Admin view for Thing model (Wells, Springs, etc.).

    Designed to replicate MS Access "Well Data Entry Form" and "Well Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all things
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published things (read-only)
    """

    # ========== Basic Configuration ==========

    identity = "thing"
    name = "Things"
    label = "Things (Wells/Springs)"
    icon = "fa fa-tint"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    sortable_fields = [
        "id",
        "name",
        "thing_type",
        "well_depth",
        "hole_depth",
        "first_visit_date",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]  # True = descending

    searchable_fields = [
        "name",
        "thing_type",
        "well_driller_name",
        "well_depth",
        "first_visit_date",
        "release_status",
        "created_at",
    ]

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
