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

    sortable_fields = [
        "id",
        "name",
        "organization",
        "role",
        "contact_type",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("name", False)]  # Alphabetical by name

    searchable_fields = [
        "name",
        "organization",
        "role",
        "contact_type",
        "release_status",
        "created_at",
    ]

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
