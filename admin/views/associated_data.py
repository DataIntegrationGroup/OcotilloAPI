from admin.views.base import OcotilloModelView


class AssociatedDataAdmin(OcotilloModelView):
    """
    Admin view for legacy AssociatedData model (NMA_AssociatedData).
    Read-only, MS Access-like listing/details.
    """

    # ========== Basic Configuration ==========
    name = "NMA Associated Data"
    label = "NMA Associated Data"
    icon = "fa fa-link"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "location_id",
        "point_id",
        "assoc_id",
        "notes",
        "formation",
        "object_id",
        "thing_id",
    ]

    sortable_fields = [
        "assoc_id",
        "object_id",
        "point_id",
    ]

    fields_default_sort = [("point_id", False), ("object_id", False)]

    searchable_fields = [
        "point_id",
        "assoc_id",
        "notes",
        "formation",
    ]

    # ========== Detail View ==========
    fields = [
        "location_id",
        "point_id",
        "assoc_id",
        "notes",
        "formation",
        "object_id",
        "thing_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "location_id": "LocationId",
        "point_id": "PointID",
        "assoc_id": "AssocID",
        "notes": "Notes",
        "formation": "Formation",
        "object_id": "OBJECTID",
        "thing_id": "ThingID",
    }

    # ========== READ ONLY ==========
    enable_publish_actions = (
        False  # hides publish/unpublish actions inherited from base
    )

    def can_create(self, request) -> bool:
        return False

    def can_edit(self, request) -> bool:
        return False

    def can_delete(self, request) -> bool:
        return False
