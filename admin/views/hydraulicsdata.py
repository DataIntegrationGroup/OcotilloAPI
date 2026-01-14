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
from admin.views.base import OcotilloModelView


class HydraulicsDataAdmin(OcotilloModelView):
    """
    Admin view for NMAHydraulicsData model.
    """

    # ========== Basic Configuration ==========

    name = "Hydraulics Data"
    label = "Hydraulics Data"
    icon = "fa fa-tint"

    can_create = False
    can_edit = False
    can_delete = False

    # ========== List View ==========

    list_fields = [
        "global_id",
        "point_id",
        "thing_id",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "test_top",
        "test_bottom",
        "t_ft2_d",
        "k_darcy",
        "data_source",
    ]

    sortable_fields = [
        "global_id",
        "point_id",
        "thing_id",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "test_top",
        "test_bottom",
        "t_ft2_d",
        "k_darcy",
        "data_source",
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
        "point_id",
        "thing_id",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "hydraulic_remarks",
        "test_top",
        "test_bottom",
        "t_ft2_d",
        "s_dimensionless",
        "ss_ft_1",
        "sy_decimalfractn",
        "kh_ft_d",
        "kv_ft_d",
        "hl_day_1",
        "hd_ft2_d",
        "cs_gal_d_ft",
        "p_decimal_fraction",
        "k_darcy",
        "data_source",
    ]

    field_labels = {
        "global_id": "GlobalID",
        "point_id": "PointID",
        "thing_id": "Thing ID",
        "hydraulic_unit": "HydraulicUnit",
        "hydraulic_unit_type": "HydraulicUnitType",
        "hydraulic_remarks": "Hydraulic Remarks",
        "test_top": "TestTop",
        "test_bottom": "TestBottom",
        "t_ft2_d": "T (ft2/d)",
        "s_dimensionless": "S (dimensionless)",
        "ss_ft_1": "Ss (ft-1)",
        "sy_decimalfractn": "Sy (decimalfractn)",
        "kh_ft_d": "KH (ft/d)",
        "kv_ft_d": "KV (ft/d)",
        "hl_day_1": "HL (day-1)",
        "hd_ft2_d": "HD (ft2/d)",
        "cs_gal_d_ft": "Cs (gal/d/ft)",
        "p_decimal_fraction": "P (decimal fraction)",
        "k_darcy": "k (darcy)",
        "data_source": "Data Source",
    }


# ============= EOF =============================================
