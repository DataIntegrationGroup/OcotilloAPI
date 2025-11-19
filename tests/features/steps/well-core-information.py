from constants import SRID_WGS84, SRID_UTM_ZONE_13N
from services.util import (
    transform_srid,
    convert_m_to_ft,
    retrieve_latest_polymorphic_history_table_record,
)

from behave import then
from geoalchemy2.shape import to_shape


@then("the response should be in JSON format")
def step_impl(context):
    assert context.response["Content-Type"] == "application/json"


# ------------------------------------------------------------------------------
# Well names and projects
# ------------------------------------------------------------------------------


@then("the response should include the well name (point ID) (i.e. NM-1234)")
def step_impl(context):
    assert "name" in context.water_well_data

    assert context.water_well_data["name"] == context.objects["wells"][0].name


@then("the response should include the project(s) or group(s) associated with the well")
def step_impl(context):
    assert "groups" in context.water_well_data

    assert (
        context.water_well_data["groups"][0]["description"]
        == context.objects["groups"][0].description
    )
    assert (
        context.water_well_data["groups"][0]["name"]
        == context.objects["groups"][0].name
    )
    assert (
        context.water_well_data["groups"][0]["project_area"]
        == context.objects["groups"][0].project_area
    )
    assert (
        context.water_well_data["groups"][0]["group_type"]
        == context.objects["groups"][0].group_type
    )


# ------------------------------------------------------------------------------
# Well Purpose and Status and Monitoring Status
# ------------------------------------------------------------------------------


@then("the response should include the purpose of the well (current use)")
def step_impl(context):
    assert "well_purposes" in context.water_well_data

    assert "Domestic" in context.water_well_data["well_purposes"]
    assert "Irrigation" in context.water_well_data["well_purposes"]

    assert (
        context.water_well_data["well_purposes"][0]
        == context.objects["wells"][0].well_purposes[0].purpose
    )
    assert (
        context.water_well_data["well_purposes"][1]
        == context.objects["wells"][0].well_purposes[1].purpose
    )


@then(
    "the response should include the well hole status of the well as the status of the hole in the ground (from previous Status field)"
)
def step_impl(context):
    assert "well_status" in context.water_well_data

    well_status_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "status_history", "Well Status"
    )
    assert context.water_well_data["well_status"] == well_status_record.status_value


@then("the response should include the monitoring frequency (new field)")
def step_impl(context):
    assert "monitoring_frequencies" in context.water_well_data

    assert len(context.water_well_data["monitoring_frequencies"]) == 1
    assert context.water_well_data["monitoring_frequencies"][0] == {
        "monitoring_frequency": "Annual",
        "start_date": "2020-01-01",
        "end_date": None,
    }


@then(
    "the response should include whether the well is currently being monitored with status text if applicable (from previous MonitoringStatus field)"
)
def step_impl(context):
    assert "monitoring_status" in context.water_well_data

    monitoring_status_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "status_history", "Monitoring Status"
    )
    assert (
        context.water_well_data["monitoring_status"]
        == monitoring_status_record.status_value
    )


# ------------------------------------------------------------------------------
# Data Lifecycle and Public Visibility
# ------------------------------------------------------------------------------


@then("the response should include the release status of the well record")
def step_impl(context):
    assert "release_status" in context.water_well_data

    assert (
        context.water_well_data["release_status"]
        == context.objects["wells"][0].release_status
    )


# ------------------------------------------------------------------------------
# Well Physical Properties
# ------------------------------------------------------------------------------


@then("the response should include the hole depth in feet")
def step_impl(context):
    assert "hole_depth" in context.water_well_data
    assert "hole_depth_unit" in context.water_well_data

    assert (
        context.water_well_data["hole_depth"] == context.objects["wells"][0].hole_depth
    )
    assert context.water_well_data["hole_depth_unit"] == "ft"


@then("the response should include the well depth in feet")
def step_impl(context):
    assert "well_depth" in context.water_well_data
    assert "well_depth_unit" in context.water_well_data

    assert (
        context.water_well_data["well_depth"] == context.objects["wells"][0].well_depth
    )
    assert context.water_well_data["well_depth_unit"] == "ft"


@then("the response should include the source of the well depth information")
def step_impl(context):
    assert "well_depth_source" in context.water_well_data

    data_provenance_records = context.objects["data_provenance"]
    well_depth_source_records = [
        r
        for r in data_provenance_records
        if r.field_name == "well_depth"
        and r.target_table == "thing"
        and r.target_id == context.objects["wells"][0].id
    ]
    well_depth_source = well_depth_source_records[0].origin_source

    assert context.water_well_data["well_depth_source"] == well_depth_source


# ------------------------------------------------------------------------------
# Measuring Point Information
# ------------------------------------------------------------------------------


@then("the response should include the description of the measuring point")
def step_impl(context):
    assert "measuring_point_description" in context.water_well_data

    assert (
        context.water_well_data["measuring_point_description"]
        == context.objects["wells"][0].measuring_point_description
    )


@then("the response should include the measuring point height in feet")
def step_impl(context):
    assert "measuring_point_height" in context.water_well_data
    assert "measuring_point_height_unit" in context.water_well_data

    assert (
        context.water_well_data["measuring_point_height"]
        == context.objects["wells"][0].measuring_point_height
    )
    assert context.water_well_data["measuring_point_height_unit"] == "ft"


# ------------------------------------------------------------------------------
# Location Information
# GeoJSON spec format RFC 7946 (Aug 2016) requires coordinates to be decimal degrees in WGS84
# ------------------------------------------------------------------------------
@then(
    "the response should include location information in GeoJSON spec format RFC 7946"
)
def step_impl(context):
    assert "current_location" in context.water_well_data
    assert "type" in context.water_well_data["current_location"]
    assert "geometry" in context.water_well_data["current_location"]
    assert "type" in context.water_well_data["current_location"]["geometry"]
    assert "coordinates" in context.water_well_data["current_location"]["geometry"]
    assert "properties" in context.water_well_data["current_location"]

    assert context.water_well_data["current_location"]["type"] == "Feature"


@then(
    'the response should include a geometry object with type "Point" and coordinates array [longitude, latitude, elevation]'
)
def step_impl(context):
    point_wkb = context.objects["locations"][0].point
    point_wkt = to_shape(point_wkb)
    latitude = point_wkt.y
    longitude = point_wkt.x
    elevation_m = context.objects["locations"][0].elevation

    assert context.water_well_data["current_location"]["geometry"] == {
        "type": "Point",
        "coordinates": [longitude, latitude, elevation_m],
    }


@then(
    "the response should include the elevation in feet with vertical datum NAVD88 in the properties"
)
def step_impl(context):
    assert "elevation" in context.water_well_data["current_location"]["properties"]
    assert "elevation_unit" in context.water_well_data["current_location"]["properties"]
    assert "vertical_datum" in context.water_well_data["current_location"]["properties"]

    elevation_ft = convert_m_to_ft(context.objects["locations"][0].elevation)

    assert (
        context.water_well_data["current_location"]["properties"]["elevation"]
        == elevation_ft
    )
    assert (
        context.water_well_data["current_location"]["properties"]["elevation_unit"]
        == "ft"
    )
    assert (
        context.water_well_data["current_location"]["properties"]["vertical_datum"]
        == "NAVD88"
    )


@then(
    "the response should include the elevation method (i.e. interpolated from digital elevation model) in the properties"
)
def step_impl(context):
    assert (
        "elevation_method" in context.water_well_data["current_location"]["properties"]
    )

    data_provenance_records = context.objects["data_provenance"]
    elevation_method_records = [
        r
        for r in data_provenance_records
        if r.field_name == "elevation"
        and r.target_table == "location"
        and r.target_id == context.objects["locations"][0].id
    ]
    elevation_method = elevation_method_records[0].collection_method
    assert (
        context.water_well_data["current_location"]["properties"]["elevation_method"]
        == elevation_method
    )


@then(
    "the response should include the UTM coordinates with datum NAD83 in the properties"
)
def step_impl(context):

    assert (
        "utm_coordinates" in context.water_well_data["current_location"]["properties"]
    )

    point_wkb = context.objects["locations"][0].point
    point_wkt = to_shape(point_wkb)
    point_utm_zone_13 = transform_srid(point_wkt, SRID_WGS84, SRID_UTM_ZONE_13N)

    assert context.water_well_data["current_location"]["properties"][
        "utm_coordinates"
    ] == {
        "easting": point_utm_zone_13.x,
        "northing": point_utm_zone_13.y,
        "utm_zone": 13,
        "horizontal_datum": "NAD83",
    }


# ------------------------------------------------------------------------------
# Alternate Identifiers
# ------------------------------------------------------------------------------


@then(
    "the response should include any alternate IDs for the well like the NMBGMR site_name (i.e. John Smith Well), USGS site number, or the OSE well ID and OSE well tag ID"
)
def step_impl(context):
    assert "alternate_ids" in context.water_well_data

    assert len(context.water_well_data["alternate_ids"]) == 3
    for item in context.water_well_data["alternate_ids"]:
        if item["alternate_organization"] == "USGS":
            assert item["relation"] == context.objects["id_links"][0].relation
            assert item["alternate_id"] == context.objects["id_links"][0].alternate_id
        elif item["alternate_organization"] == "NMOSE":
            assert item["relation"] == context.objects["id_links"][1].relation
            assert item["alternate_id"] == context.objects["id_links"][1].alternate_id
        elif item["alternate_organization"] == "NMBGMR":
            assert item["relation"] == context.objects["id_links"][2].relation
            assert item["alternate_id"] == context.objects["id_links"][2].alternate_id
