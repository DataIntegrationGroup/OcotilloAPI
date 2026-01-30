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
HydraulicsDataAdmin view for legacy NMA_HydraulicsData.
"""

from starlette.requests import Request

from admin.views.base import OcotilloModelView


class HydraulicsDataAdmin(OcotilloModelView):
    """
    Admin view for NMA_HydraulicsData model.
    """

    # ========== Basic Configuration ==========

    name = "NMA Hydraulics Data"
    label = "NMA Hydraulics Data"
    icon = "fa fa-tint"

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    # ========== List View ==========

    list_fields = [
        "global_id",
        "well_id",
        "point_id",
        "data_source",
        "thing_id",
        "object_id",
        "cs_gal_d_ft",
        "hd_ft2_d",
        "hl_day_1",
        "kh_ft_d",
        "kv_ft_d",
        "p_decimal_fraction",
        "s_dimensionless",
        "ss_ft_1",
        "sy_decimalfractn",
        "t_ft2_d",
        "k_darcy",
        "test_bottom",
        "test_top",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "hydraulic_remarks",
    ]

    sortable_fields = [
        "global_id",
        "well_id",
        "point_id",
        "data_source",
        "thing_id",
        "object_id",
        "cs_gal_d_ft",
        "hd_ft2_d",
        "hl_day_1",
        "kh_ft_d",
        "kv_ft_d",
        "p_decimal_fraction",
        "s_dimensionless",
        "ss_ft_1",
        "sy_decimalfractn",
        "t_ft2_d",
        "k_darcy",
        "test_bottom",
        "test_top",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "hydraulic_remarks",
    ]

    searchable_fields = [
        "global_id",
        "point_id",
        "hydraulic_unit",
        "hydraulic_remarks",
        "data_source",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "global_id",
        "well_id",
        "point_id",
        "data_source",
        "thing_id",
        "object_id",
        "cs_gal_d_ft",
        "hd_ft2_d",
        "hl_day_1",
        "kh_ft_d",
        "kv_ft_d",
        "p_decimal_fraction",
        "s_dimensionless",
        "ss_ft_1",
        "sy_decimalfractn",
        "t_ft2_d",
        "k_darcy",
        "test_bottom",
        "test_top",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "hydraulic_remarks",
    ]

    field_labels = {
        "global_id": "GlobalID",
        "well_id": "WellID",
        "point_id": "PointID",
        "thing_id": "Thing ID",
        "hydraulic_unit": "Hydraulic Unit",
        "hydraulic_unit_type": "HydraulicUnit Type",
        "hydraulic_remarks": "Hydraulic Remarks",
        "test_top": "Test Top",
        "test_bottom": "Test Bottom",
        "t_ft2_d": "T (ft2/d)",
        "s_dimensionless": "S (dimensionless)",
        "ss_ft_1": "Ss (ft-1)",
        "sy_decimalfractn": "Sy (decimal fraction)",
        "kh_ft_d": "KH (ft/d)",
        "kv_ft_d": "KV (ft/d)",
        "hl_day_1": "HL (day-1)",
        "hd_ft2_d": "HD (ft2/d)",
        "cs_gal_d_ft": "Cs (gal/d/ft)",
        "p_decimal_fraction": "P (decimal fraction)",
        "k_darcy": "k (darcy)",
        "data_source": "Data Source",
        "object_id": "OBJECTID",
    }


# ============= EOF =============================================
