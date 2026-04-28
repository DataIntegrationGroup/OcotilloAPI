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
SurfaceWaterDataAdmin view for OcotilloAPI.
"""

from admin.views.base import OcotilloModelView


class SurfaceWaterDataAdmin(OcotilloModelView):
    """
    Admin view for SurfaceWaterData legacy model.
    """

    name = "NMA Surface Water Data"
    label = "NMA Surface Water Data"
    icon = "fa fa-water"
    enable_publish_actions = False

    sortable_fields = [
        "surface_id",
        "point_id",
        "date_measured",
        "discharge",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
    ]

    fields_default_sort = [("date_measured", True)]

    searchable_fields = [
        "point_id",
        "discharge",
        "formation_zone",
        "aq_class",
        "data_source",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "surface_id",
        "point_id",
        "object_id",
        "date_measured",
        "discharge",
        "discharge_rate",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
        "site_notes",
        "field_method_notes",
        "source_notes",
        "data_source",
    ]

    # ========== READ ONLY ==========
    enable_publish_actions = (
        False  # hides publish/unpublish actions inherited from base
    )

    def can_create(self, request) -> bool:
        return False

    def can_edit(self, request) -> bool:
        return False

    def can_delete(self, request) -> bool:
        return False


# ============= EOF =============================================
