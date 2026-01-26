"""
SoilRockResultsAdmin view for legacy NMA_Soil_Rock_Results.
"""

from admin.views.base import OcotilloModelView


class SoilRockResultsAdmin(OcotilloModelView):
    """
    Read-only admin view for SoilRockResults legacy model.
    """

    # ========== Basic Configuration ==========
    name = "NMA Soil Rock Results"
    label = "NMA Soil Rock Results"
    icon = "fa fa-mountain"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "id",
        "point_id",
        "sample_type",
        "date_sampled",
        "d13c",
        "d18o",
        "sampled_by",
        "thing_id",
    ]

    sortable_fields = [
        "id",
        "point_id",
    ]

    searchable_fields = [
        "point_id",
        "sample_type",
        "date_sampled",
        "sampled_by",
    ]

    fields_default_sort = [("id", True)]

    # ========== Detail View ==========
    fields = [
        "id",
        "point_id",
        "sample_type",
        "date_sampled",
        "d13c",
        "d18o",
        "sampled_by",
        "thing_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "id": "id",
        "point_id": "Point_ID",
        "sample_type": "Sample Type",
        "date_sampled": "Date Sampled",
        "d13c": "d13C",
        "d18o": "d18O",
        "sampled_by": "Sampled by",
        "thing_id": "ThingID",
    }
