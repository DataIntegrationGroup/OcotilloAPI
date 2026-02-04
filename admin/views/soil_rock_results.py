"""
SoilRockResultsAdmin view for legacy NMA_Soil_Rock_Results.

Already has Integer PK. Updated for legacy column rename:
- point_id -> nma_point_id
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

    # Integer PK (already correct)
    pk_attr = "id"
    pk_type = int

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "id",
        "nma_point_id",
        "sample_type",
        "date_sampled",
        "d13c",
        "d18o",
        "sampled_by",
        "thing_id",
    ]

    sortable_fields = [
        "id",
        "nma_point_id",
    ]

    searchable_fields = [
        "nma_point_id",
        "sample_type",
        "date_sampled",
        "sampled_by",
    ]

    fields_default_sort = [("id", True)]

    # ========== Detail View ==========
    fields = [
        "id",
        "nma_point_id",
        "sample_type",
        "date_sampled",
        "d13c",
        "d18o",
        "sampled_by",
        "thing_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "id": "ID",
        "nma_point_id": "NMA Point_ID (Legacy)",
        "sample_type": "Sample Type",
        "date_sampled": "Date Sampled",
        "d13c": "d13C",
        "d18o": "d18O",
        "sampled_by": "Sampled by",
        "thing_id": "ThingID",
    }
