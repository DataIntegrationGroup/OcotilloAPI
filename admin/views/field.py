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
Field admin views for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class FieldEventAdmin(OcotilloModelView):
    """
    Admin view for FieldEvent model.
    """

    name = "Field Events"
    label = "Field Events"
    icon = "fa fa-calendar"

    column_list = [
        "id",
        "thing_id",
        "event_date",
        "notes",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "thing_id",
        "event_date",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("event_date", True)

    search_fields = [
        "notes",
    ]

    column_filters = [
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "id",
        "thing_id",
        "event_date",
        "notes",
        "release_status",
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
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
    ]

    labels = {
        "id": "Field Event ID",
        "thing_id": "Thing",
        "event_date": "Event Date",
        "notes": "Notes",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


class FieldActivityAdmin(OcotilloModelView):
    """
    Admin view for FieldActivity model.
    """

    name = "Field Activities"
    label = "Field Activities"
    icon = "fa fa-tasks"

    column_list = [
        "id",
        "field_event_id",
        "activity_type",
        "notes",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "field_event_id",
        "activity_type",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)

    search_fields = [
        "notes",
    ]

    column_filters = [
        "activity_type",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "id",
        "field_event_id",
        "activity_type",
        "notes",
        "release_status",
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
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
    ]

    labels = {
        "id": "Field Activity ID",
        "field_event_id": "Field Event",
        "activity_type": "Activity Type",
        "notes": "Notes",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


class FieldEventParticipantAdmin(OcotilloModelView):
    """
    Admin view for FieldEventParticipant model.
    """

    name = "Field Event Participants"
    label = "Field Event Participants"
    icon = "fa fa-users"

    column_list = [
        "id",
        "field_event_id",
        "contact_id",
        "participant_role",
        "release_status",
        "created_at",
        "updated_by_name",
    ]

    column_sortable_list = [
        "id",
        "field_event_id",
        "contact_id",
        "participant_role",
        "release_status",
        "created_at",
    ]

    column_default_sort = ("created_at", True)

    column_filters = [
        "participant_role",
        "release_status",
        "created_at",
    ]

    can_export = True
    export_types = ["csv", "excel"]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "id",
        "field_event_id",
        "contact_id",
        "participant_role",
        "release_status",
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
    ]

    exclude_fields_from_edit = [
        "id",
        "created_at",
        "created_by_id",
        "created_by_name",
    ]

    labels = {
        "id": "Participant ID",
        "field_event_id": "Field Event",
        "contact_id": "Contact",
        "participant_role": "Participant Role",
        "release_status": "Release Status",
        "created_at": "Created At",
        "created_by_name": "Created By",
        "updated_by_name": "Updated By",
    }


# ============= EOF =============================================
