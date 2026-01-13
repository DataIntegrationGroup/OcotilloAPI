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
Lexicon admin views for NMSampleLocations.
"""
from admin.views.base import OcotilloModelView


class LexiconTermAdmin(OcotilloModelView):
    """
    Admin view for LexiconTerm model.
    """

    name = "Lexicon Terms"
    label = "Lexicon Terms"
    icon = "fa fa-book"
    enable_publish_actions = False

    sortable_fields = [
        "id",
        "term",
    ]

    fields_default_sort = [("term", False)]

    searchable_fields = [
        "term",
        "definition",
    ]

    fields = [
        "id",
        "term",
        "definition",
    ]

    exclude_fields_from_create = [
        "id",
    ]

    exclude_fields_from_edit = [
        "id",
    ]


class LexiconCategoryAdmin(OcotilloModelView):
    """
    Admin view for LexiconCategory model.
    """

    name = "Lexicon Categories"
    label = "Lexicon Categories"
    icon = "fa fa-tags"
    enable_publish_actions = False

    sortable_fields = [
        "id",
        "name",
    ]

    fields_default_sort = [("name", False)]

    searchable_fields = [
        "name",
        "description",
    ]

    fields = [
        "id",
        "name",
        "description",
    ]

    exclude_fields_from_create = [
        "id",
    ]

    exclude_fields_from_edit = [
        "id",
    ]


# ============= EOF =============================================
