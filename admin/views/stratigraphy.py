"""
StratigraphyAdmin view for legacy Chemistry_SampleInfo.
"""

from admin.views.base import OcotilloModelView


class StratigraphyAdmin(OcotilloModelView):
    """
    Read-only admin view for Stratigraphy legacy model.
    """

    # ========== Basic Configuration ==========
    name = "NMA Stratigraphy"
    label = "NMA Stratigraphy"
    icon = "fa fa-layer-group"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========

    sortable_fields = [
        "global_id",
        "object_id",
        "point_id",
    ]

    fields_default_sort = [("point_id", False), ("strat_top", False)]

    searchable_fields = [
        "point_id",
        "global_id",
        "unit_identifier",
        "lithology",
        "lithologic_modifier",
        "contributing_unit",
        "strat_source",
        "strat_notes",
    ]

    # ========== Form View ==========

    fields = [
        "global_id",
        "well_id",
        "point_id",
        "thing_id",
        "strat_top",
        "strat_bottom",
        "unit_identifier",
        "lithology",
        "lithologic_modifier",
        "contributing_unit",
        "strat_source",
        "strat_notes",
        "object_id",
    ]

    exclude_fields_from_create = [
        "object_id",
    ]

    exclude_fields_from_edit = [
        "object_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "global_id": "GlobalID",
        "well_id": "WellID",
        "point_id": "PointID",
        "thing_id": "ThingID",
        "strat_top": "StratTop",
        "strat_bottom": "StratBottom",
        "unit_identifier": "UnitIdentifier",
        "lithology": "Lithology",
        "lithologic_modifier": "LithologicModifier",
        "contributing_unit": "ContributingUnit",
        "strat_source": "StratSource",
        "strat_notes": "StratNotes",
        "object_id": "OBJECTID",
    }
