# ===============================================================================
# Copyright 2026
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
ChemistrySampleInfoAdmin view for legacy Chemistry_SampleInfo.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_sample_pt_id: Legacy UUID PK (SamplePtID), UNIQUE for audit
- nma_wclab_id: Legacy WCLab_ID
- nma_sample_point_id: Legacy SamplePointID
- nma_object_id: Legacy OBJECTID, UNIQUE
- nma_location_id: Legacy LocationId UUID (for audit trail)

FK Change (2026-01):
- thing_id: Integer FK to Thing.id
"""

from starlette.requests import Request
from starlette_admin import HasOne

from admin.views.base import OcotilloModelView


class ChemistrySampleInfoAdmin(OcotilloModelView):
    """
    Admin view for ChemistrySampleInfo model.
    """

    # ========== Basic Configuration ==========

    name = "NMA Chemistry Sample Info"
    label = "NMA Chemistry Sample Info"
    icon = "fa fa-flask"

    # Integer PK
    pk_attr = "id"
    pk_type = int

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # ========== List View ==========

    list_fields = [
        "id",
        "nma_sample_pt_id",
        "nma_wclab_id",
        "nma_sample_point_id",
        "nma_object_id",
        "nma_location_id",
        "thing_id",
        HasOne("thing", identity="thing"),
        "collection_date",
        "collection_method",
        "collected_by",
        "analyses_agency",
        "sample_type",
        "sample_material_not_h2o",
        "water_type",
        "study_sample",
        "data_source",
        "data_quality",
        "public_release",
        "added_day_to_date",
        "added_month_day_to_date",
        "sample_notes",
    ]

    sortable_fields = [
        "id",
        "nma_sample_pt_id",
        "nma_wclab_id",
        "nma_sample_point_id",
        "nma_object_id",
        "collection_date",
        "sample_type",
        "data_source",
        "data_quality",
        "public_release",
    ]

    fields_default_sort = [("collection_date", True)]

    searchable_fields = [
        "nma_sample_pt_id",
        "nma_wclab_id",
        "nma_sample_point_id",
        "collection_date",
        "collected_by",
        "analyses_agency",
        "sample_type",
        "sample_material_not_h2o",
        "water_type",
        "study_sample",
        "data_source",
        "data_quality",
        "public_release",
        "sample_notes",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "nma_sample_pt_id",
        "nma_wclab_id",
        "nma_sample_point_id",
        "nma_object_id",
        "nma_location_id",
        "thing_id",
        HasOne("thing", identity="thing"),
        "collection_date",
        "collection_method",
        "collected_by",
        "analyses_agency",
        "sample_type",
        "sample_material_not_h2o",
        "water_type",
        "study_sample",
        "data_source",
        "data_quality",
        "public_release",
        "added_day_to_date",
        "added_month_day_to_date",
        "sample_notes",
    ]

    field_labels = {
        "id": "ID",
        "nma_sample_pt_id": "NMA SamplePtID (Legacy)",
        "nma_wclab_id": "NMA WCLab_ID (Legacy)",
        "nma_sample_point_id": "NMA SamplePointID (Legacy)",
        "nma_object_id": "NMA OBJECTID (Legacy)",
        "nma_location_id": "NMA LocationId (Legacy)",
        "thing_id": "Thing ID",
        "collection_date": "Collection Date",
        "collection_method": "Collection Method",
        "collected_by": "Collected By",
        "analyses_agency": "Analyses Agency",
        "sample_type": "Sample Type",
        "sample_material_not_h2o": "Sample Material Not H2O",
        "water_type": "Water Type",
        "study_sample": "Study Sample",
        "data_source": "Data Source",
        "data_quality": "Data Quality",
        "public_release": "Public Release",
        "added_day_to_date": "Added Day to Date",
        "added_month_day_to_date": "Added Month/Day to Date",
        "sample_notes": "Sample Notes",
    }


# ============= EOF =============================================
