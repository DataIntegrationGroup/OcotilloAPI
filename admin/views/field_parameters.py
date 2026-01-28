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
FieldParametersAdmin view for legacy NMA_FieldParameters.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy UUID PK (GlobalID), UNIQUE for audit
- chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
- nma_sample_pt_id: Legacy UUID FK (SamplePtID) for audit
- nma_sample_point_id: Legacy SamplePointID string
- nma_object_id: Legacy OBJECTID
- nma_wclab_id: Legacy WCLab_ID
"""

from admin.views.base import OcotilloModelView


class FieldParametersAdmin(OcotilloModelView):
    """
    Admin view for FieldParameters model.
    """

    # ========== Basic Configuration ==========

    name = "Field Parameters"
    label = "Field Parameters"
    icon = "fa fa-tachometer"

    # Integer PK
    pk_attr = "id"
    pk_type = int

    can_create = False
    can_edit = False
    can_delete = False

    # ========== List View ==========

    list_fields = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "analyses_agency",
        "nma_wclab_id",
        "nma_object_id",
    ]

    sortable_fields = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "analyses_agency",
        "nma_wclab_id",
        "nma_object_id",
    ]

    fields_default_sort = [("nma_sample_point_id", True)]

    searchable_fields = [
        "nma_global_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "field_parameter",
        "units",
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
        "field_parameter",
        "sample_value",
        "units",
        "notes",
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
        "field_parameter": "FieldParameter",
        "sample_value": "SampleValue",
        "units": "Units",
        "notes": "Notes",
        "nma_object_id": "NMA OBJECTID (Legacy)",
        "analyses_agency": "AnalysesAgency",
        "nma_wclab_id": "NMA WCLab_ID (Legacy)",
    }


# ============= EOF =============================================
