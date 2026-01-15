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

    sortable_fields = [
        "id",
        "thing_id",
        "event_date",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("event_date", True)]

    searchable_fields = [
        "notes",
        "release_status",
        "created_at",
    ]

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


class FieldActivityAdmin(OcotilloModelView):
    """
    Admin view for FieldActivity model.
    """

    name = "Field Activities"
    label = "Field Activities"
    icon = "fa fa-tasks"

    sortable_fields = [
        "id",
        "field_event_id",
        "activity_type",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]

    searchable_fields = [
        "notes",
        "activity_type",
        "release_status",
        "created_at",
    ]

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


class FieldEventParticipantAdmin(OcotilloModelView):
    """
    Admin view for FieldEventParticipant model.
    """

    name = "Field Event Participants"
    label = "Field Event Participants"
    icon = "fa fa-users"

    sortable_fields = [
        "id",
        "field_event_id",
        "contact_id",
        "participant_role",
        "release_status",
        "created_at",
    ]

    fields_default_sort = [("created_at", True)]

    searchable_fields = [
        "participant_role",
        "release_status",
        "created_at",
    ]

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


# ============= EOF =============================================
