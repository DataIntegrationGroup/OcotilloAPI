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
MajorChemistryAdmin view for legacy NMA_MajorChemistry.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy UUID PK (GlobalID), UNIQUE for audit
- chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
- nma_sample_pt_id: Legacy UUID FK (SamplePtID) for audit
- nma_sample_point_id: Legacy SamplePointID string
- nma_object_id: Legacy OBJECTID
- nma_wclab_id: Legacy WCLab_ID
"""

from starlette.requests import Request
from starlette_admin.fields import HasOne

from admin.views.base import OcotilloModelView


class MajorChemistryAdmin(OcotilloModelView):
    """
    Admin view for NMA_MajorChemistry model.
    """

    # ========== Basic Configuration ==========

    identity = "n-m-a_-major-chemistry"
    name = "NMA Major Chemistry"
    label = "NMA Major Chemistry"
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
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        HasOne("chemistry_sample_info", identity="n-m-a_-chemistry_-sample-info"),
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "notes",
        "volume",
        "volume_unit",
        "nma_object_id",
        "analyses_agency",
        "nma_wclab_id",
    ]

    sortable_fields = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "notes",
        "volume",
        "volume_unit",
        "nma_object_id",
        "analyses_agency",
        "nma_wclab_id",
    ]

    fields_default_sort = [("analysis_date", True)]

    searchable_fields = [
        "nma_global_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "analyte",
        "symbol",
        "analysis_method",
        "notes",
        "analyses_agency",
        "nma_wclab_id",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        HasOne("chemistry_sample_info", identity="n-m-a_-chemistry_-sample-info"),
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "notes",
        "volume",
        "volume_unit",
        "nma_object_id",
        "analyses_agency",
        "nma_wclab_id",
    ]

    field_labels = {
        "id": "ID",
        "nma_global_id": "NMA GlobalID (Legacy)",
        "chemistry_sample_info_id": "Chemistry Sample Info ID",
        "nma_sample_pt_id": "NMA SamplePtID (Legacy)",
        "nma_sample_point_id": "NMA SamplePointID (Legacy)",
        "chemistry_sample_info": "Chemistry Sample Info",
        "analyte": "Analyte",
        "symbol": "Symbol",
        "sample_value": "Sample Value",
        "units": "Units",
        "uncertainty": "Uncertainty",
        "analysis_method": "Analysis Method",
        "analysis_date": "Analysis Date",
        "notes": "Notes",
        "volume": "Volume",
        "volume_unit": "Volume Unit",
        "nma_object_id": "NMA OBJECTID (Legacy)",
        "analyses_agency": "Analyses Agency",
        "nma_wclab_id": "NMA WCLab_ID (Legacy)",
    }


# ============= EOF =============================================
