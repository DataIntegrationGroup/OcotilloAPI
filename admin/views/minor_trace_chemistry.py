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
MinorTraceChemistryAdmin view for legacy NMA_MinorTraceChemistry.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy UUID PK (GlobalID), UNIQUE for audit
- chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
- nma_chemistry_sample_info_uuid: Legacy UUID FK for audit
"""

from starlette.requests import Request
from starlette_admin.fields import HasOne

from admin.views.base import OcotilloModelView


class MinorTraceChemistryAdmin(OcotilloModelView):
    """
    Admin view for NMA_MinorTraceChemistry model.
    """

    # ========== Basic Configuration ==========

    identity = "n-m-a_-minor-trace-chemistry"
    name = "Minor Trace Chemistry"
    label = "Minor Trace Chemistry"
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
        HasOne("chemistry_sample_info", identity="n-m-a_-chemistry_-sample-info"),
        "nma_chemistry_sample_info_uuid",
        "analyte",
        "sample_value",
        "units",
        "symbol",
        "analysis_date",
        "analyses_agency",
    ]

    sortable_fields = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "analyte",
        "sample_value",
        "units",
        "symbol",
        "analysis_date",
        "analyses_agency",
    ]

    fields_default_sort = [("analysis_date", True)]

    searchable_fields = [
        "nma_global_id",
        "analyte",
        "symbol",
        "analysis_method",
        "notes",
        "analyses_agency",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "id",
        "nma_global_id",
        HasOne("chemistry_sample_info", identity="n-m-a_-chemistry_-sample-info"),
        "nma_chemistry_sample_info_uuid",
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
        "analyses_agency",
    ]

    field_labels = {
        "id": "ID",
        "nma_global_id": "NMA GlobalID (Legacy)",
        "chemistry_sample_info": "Chemistry Sample Info",
        "chemistry_sample_info_id": "Chemistry Sample Info ID",
        "nma_chemistry_sample_info_uuid": "NMA Chemistry Sample Info UUID (Legacy)",
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
        "analyses_agency": "Analyses Agency",
    }


# ============= EOF =============================================
