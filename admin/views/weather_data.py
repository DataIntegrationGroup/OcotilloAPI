from admin.views.base import OcotilloModelView


class WeatherDataAdmin(OcotilloModelView):
    """
    Admin view for legacy WeatherData model (NMA_WeatherData).
    """

    # ========== Basic Configuration ==========
    name = "NMA Weather Data"
    label = "NMA Weather Data"
    icon = "fa fa-cloud-sun"

    # Pagination
    page_size = 50
    page_size_options = [25, 50, 100, 200]

    # ========== List View ==========
    list_fields = [
        "location_id",
        "point_id",
        "weather_id",
        "object_id",
    ]

    sortable_fields = [
        "object_id",
        "point_id",
    ]

    fields_default_sort = [("point_id", False), ("object_id", False)]

    searchable_fields = [
        "point_id",
        "weather_id",
    ]

    # ========== Detail View ==========
    fields = [
        "location_id",
        "point_id",
        "weather_id",
        "object_id",
    ]

    # ========== Legacy Field Labels ==========
    field_labels = {
        "location_id": "LocationId",
        "point_id": "PointID",
        "weather_id": "WeatherID",
        "object_id": "OBJECTID",
    }
