from admin.views.base import OcotilloModelView


class WeatherPhotosAdmin(OcotilloModelView):
    """
    Admin view for legacy WeatherPhotos model (NMA_WeatherPhotos).
    """

    # ========== Basic Configuration ==========
    name = "NMA Weather Photos"
    label = "NMA Weather Photos"
    icon = "fa fa-cloud"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "weather_id",
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
        "ole_path",
    ]

    # ========== Detail View ==========
    fields = [
        "weather_id",
        "point_id",
        "ole_path",
        "object_id",
        "global_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "weather_id": "WeatherID",
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
