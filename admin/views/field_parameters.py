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

    can_create = False
    can_edit = False
    can_delete = False

    # ========== List View ==========

    list_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "object_id",
        "analyses_agency",
        "wc_lab_id",
    ]

    sortable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "analyses_agency",
        "wc_lab_id",
        "object_id",
    ]

    fields_default_sort = [("sample_point_id", True)]

    searchable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "field_parameter",
        "units",
        "notes",
        "analyses_agency",
        "wc_lab_id",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "object_id",
        "analyses_agency",
        "wc_lab_id",
    ]

    field_labels = {
        "global_id": "GlobalID",
        "sample_pt_id": "SamplePtID",
        "sample_point_id": "SamplePointID",
        "field_parameter": "FieldParameter",
        "sample_value": "SampleValue",
        "units": "Units",
        "notes": "Notes",
        "object_id": "OBJECTID",
        "analyses_agency": "AnalysesAgency",
        "wc_lab_id": "WCLab_ID",
    }


# ============= EOF =============================================
