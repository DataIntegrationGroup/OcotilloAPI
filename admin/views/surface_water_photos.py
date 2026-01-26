from admin.views.base import OcotilloModelView


class SurfaceWaterPhotosAdmin(OcotilloModelView):
    """
    Admin view for legacy SurfaceWaterPhotos model (NMA_SurfaceWaterPhotos).
    """

    # ========== Basic Configuration ==========
    name = "NMA Surface Water Photos"
    label = "NMA Surface Water Photos"
    icon = "fa fa-water"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "surface_id",
        "point_id",
        "ole_path",
        "object_id",
        "global_id",
    ]

    sortable_fields = [
        "global_id",
        "object_id",
        "point_id",
    ]

    fields_default_sort = [("point_id", False), ("object_id", False)]

    searchable_fields = [
        "point_id",
        "global_id",
        "ole_path",
    ]

    # ========== Detail View ==========
    fields = [
        "surface_id",
        "point_id",
        "ole_path",
        "object_id",
        "global_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "surface_id": "SurfaceID",
        "point_id": "PointID",
        "ole_path": "OLEPath",
        "object_id": "OBJECTID",
        "global_id": "GlobalID",
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
