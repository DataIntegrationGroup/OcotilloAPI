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
"""

import uuid

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
    pk_attr = "global_id"
    pk_type = uuid.UUID

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # ========== List View ==========

    list_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
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
        "object_id",
        "analyses_agency",
        "wclab_id",
    ]

    sortable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
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
        "object_id",
        "analyses_agency",
        "wclab_id",
    ]

    fields_default_sort = [("analysis_date", True)]

    searchable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "analyte",
        "symbol",
        "analysis_method",
        "notes",
        "analyses_agency",
        "wclab_id",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
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
        "object_id",
        "analyses_agency",
        "wclab_id",
    ]

    field_labels = {
        "global_id": "GlobalID",
        "sample_pt_id": "SamplePtID",
        "sample_point_id": "SamplePointID",
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
        "object_id": "OBJECTID",
        "analyses_agency": "Analyses Agency",
        "wclab_id": "WCLab_ID",
    }


# ============= EOF =============================================
