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
RadionuclidesAdmin view for legacy NMA_Radionuclides.
"""

from admin.views.base import OcotilloModelView


class RadionuclidesAdmin(OcotilloModelView):
    """
    Admin view for NMA_Radionuclides model.
    """

    # ========== Basic Configuration ==========

    name = "Radionuclides"
    label = "Radionuclides"
    icon = "fa fa-radiation"

    can_create = False
    can_edit = False
    can_delete = False

    # ========== List View ==========

    list_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "thing_id",
        "analyte",
        "sample_value",
        "units",
        "analysis_date",
        "analyses_agency",
    ]

    sortable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "thing_id",
        "analyte",
        "sample_value",
        "units",
        "analysis_date",
        "analyses_agency",
        "wclab_id",
        "object_id",
    ]

    fields_default_sort = [("analysis_date", True)]

    searchable_fields = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "analyte",
        "symbol",
        "analysis_method",
        "analysis_date",
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
        "thing_id",
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
        "thing_id": "Thing ID",
        "analyte": "Analyte",
        "symbol": "Symbol",
        "sample_value": "SampleValue",
        "units": "Units",
        "uncertainty": "Uncertainty",
        "analysis_method": "AnalysisMethod",
        "analysis_date": "AnalysisDate",
        "notes": "Notes",
        "volume": "Volume",
        "volume_unit": "VolumeUnit",
        "object_id": "OBJECTID",
        "analyses_agency": "AnalysesAgency",
        "wclab_id": "WCLab_ID",
    }


# ============= EOF =============================================
