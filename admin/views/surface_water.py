"""
SurfaceWaterDataAdmin view for NMSampleLocations.
"""

from admin.views.base import OcotilloModelView


class SurfaceWaterDataAdmin(OcotilloModelView):
    """
    Admin view for SurfaceWaterData legacy model.
    """

    name = "NMA Surface Water Data"
    label = "NMA Surface Water Data"
    icon = "fa fa-water"
    enable_publish_actions = False

    sortable_fields = [
        "surface_id",
        "point_id",
        "date_measured",
        "discharge",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
    ]

    fields_default_sort = [("date_measured", True)]

    searchable_fields = [
        "point_id",
        "discharge",
        "formation_zone",
        "aq_class",
        "data_source",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
    ]

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    fields = [
        "surface_id",
        "point_id",
        "object_id",
        "date_measured",
        "discharge",
        "discharge_rate",
        "discharge_units",
        "discharge_method",
        "discharge_source",
        "formation_zone",
        "aq_class",
        "site_notes",
        "field_method_notes",
        "source_notes",
        "data_source",
    ]
