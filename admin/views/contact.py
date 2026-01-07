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
ContactAdmin view for NMSampleLocations.

Provides MS Access-like interface for CRUD operations on Contact (Owners) model.
"""
from admin.views.base import OcotilloModelView


class ContactAdmin(OcotilloModelView):
    """
    Admin view for Contact model (Well Owners/Managers).

    Designed to replicate MS Access "Owners Data Entry Form" and "Owners Datasheet View".

    Permission Model:
        - Admin: Can create, edit, delete all contacts
        - Editor: Can create and edit, cannot delete
        - Viewer: Can only view published contacts (read-only)
    """

    # ========== Basic Configuration ==========

    name = "Contacts"
    label = "Contacts (Owners)"
    icon = "fa fa-users"

    # ========== List View (MS Access Datasheet View Equivalent) ==========

    column_list = [
        "id",
        "name",
        "organization",
        "role",
        "contact_type",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "name",
        "organization",
        "role",
        "contact_type",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("name", False)  # Alphabetical by name

    search_fields = [
        "name",
        "organization",
        "role",
    ]

    column_filters = [
        "organization",
        "role",
        "contact_type",
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
        # Contact Information
        "name",
        "organization",
        "role",
        "contact_type",
        # Release Status
        "release_status",
        # Audit Fields
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        # Legacy Migration Fields
        "nma_pk_owners",
        "nma_pk_waterlevels",
    ]

    exclude_fields_from_create = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "updated_by_id",
        "updated_by_name",
        "nma_pk_owners",
        "nma_pk_waterlevels",
        # Exclude complex relationships (manage separately)
        "phones",
        "emails",
        "addresses",
        "incomplete_nma_phones",
        "permissions",
        "author_associations",
        "thing_associations",
        "field_event_participants",
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
        "nma_pk_owners",
        "nma_pk_waterlevels",
        # Exclude complex relationships (manage separately)
        "phones",
        "emails",
        "addresses",
        "incomplete_nma_phones",
        "permissions",
        "author_associations",
        "thing_associations",
        "field_event_participants",
    ]

    # ========== Field Labels and Help Text ==========

    labels = {
        "id": "Contact ID",
        "name": "Name",
        "organization": "Organization",
        "role": "Role",
        "contact_type": "Contact Type",
        "release_status": "Release Status",
        "nma_pk_owners": "AMPAPI Owners ID (Legacy)",
        "nma_pk_waterlevels": "AMPAPI WaterLevels ID (Legacy)",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }

    help_texts = {
        "name": "Full name of the contact (First Last)",
        "organization": "Organization or agency the contact is affiliated with",
        "role": "Role of the contact (e.g., 'Owner', 'Measurer', 'Manager')",
        "contact_type": "Type of contact (e.g., 'Primary', 'Secondary')",
        "release_status": "'draft' (internal only) or 'published' (public)",
    }
