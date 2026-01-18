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
"""

from admin.views.base import OcotilloModelView


class ChemistrySampleInfoAdmin(OcotilloModelView):
    """
    Admin view for ChemistrySampleInfo model.
    """

    # ========== Basic Configuration ==========

    name = "Chemistry Sample Info"
    label = "Chemistry Sample Info"
    icon = "fa fa-flask"

    # ========== List View ==========

    sortable_fields = [
        "sample_pt_id",
        "object_id",
        "sample_point_id",
        "wclab_id",
        "collection_date",
        "sample_type",
        "data_source",
        "data_quality",
        "public_release",
    ]

    fields_default_sort = [("collection_date", True)]

    searchable_fields = [
        "sample_point_id",
        "sample_pt_id",
        "wclab_id",
        "collected_by",
        "analyses_agency",
        "sample_notes",
        "collection_date",
        "sample_type",
        "sample_material_not_h2o",
        "water_type",
        "study_sample",
        "data_source",
        "data_quality",
        "public_release",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== Form View ==========

    fields = [
        "sample_pt_id",
        "sample_point_id",
        "object_id",
        "wclab_id",
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

    exclude_fields_from_create = [
        "object_id",
    ]

    exclude_fields_from_edit = [
        "object_id",
    ]


# ============= EOF =============================================
