"""
StratigraphyAdmin view for legacy stratigraphy.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy UUID PK (GlobalID), UNIQUE for audit
- nma_well_id: Legacy WellID UUID
- nma_point_id: Legacy PointID string
- nma_object_id: Legacy OBJECTID, UNIQUE
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

    # Integer PK
    pk_attr = "id"
    pk_type = int

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========

    sortable_fields = [
        "id",
        "nma_global_id",
        "nma_object_id",
        "nma_point_id",
    ]

    fields_default_sort = [("nma_point_id", False), ("strat_top", False)]

    searchable_fields = [
        "nma_point_id",
        "nma_global_id",
        "unit_identifier",
        "lithology",
        "lithologic_modifier",
        "contributing_unit",
        "strat_source",
        "strat_notes",
    ]

    # ========== Form View ==========

    fields = [
        "id",
        "nma_global_id",
        "nma_well_id",
        "nma_point_id",
        "thing_id",
        "strat_top",
        "strat_bottom",
        "unit_identifier",
        "lithology",
        "lithologic_modifier",
        "contributing_unit",
        "strat_source",
        "strat_notes",
        "nma_object_id",
    ]

    exclude_fields_from_create = [
        "id",
        "nma_object_id",
    ]

    exclude_fields_from_edit = [
        "id",
        "nma_object_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "id": "ID",
        "nma_global_id": "NMA GlobalID (Legacy)",
        "nma_well_id": "NMA WellID (Legacy)",
        "nma_point_id": "NMA PointID (Legacy)",
        "thing_id": "ThingID",
        "strat_top": "StratTop",
        "strat_bottom": "StratBottom",
        "unit_identifier": "UnitIdentifier",
        "lithology": "Lithology",
        "lithologic_modifier": "LithologicModifier",
        "contributing_unit": "ContributingUnit",
        "strat_source": "StratSource",
        "strat_notes": "StratNotes",
        "nma_object_id": "NMA OBJECTID (Legacy)",
    }
