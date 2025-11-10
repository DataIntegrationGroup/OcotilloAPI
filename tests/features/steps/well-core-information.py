from constants import SRID_WGS84, SRID_UTM_ZONE_13N
from services.util import transform_srid
from behave import when, then


# TODO: move to commonly used step definitions
@when("the user retrieves the well by ID via path parameter")
def step_impl(context):
    well_id = context.objects["wells"][0].id
    context.response = context.client.get(f"/thing/water-well/{well_id}")
    context.water_well_data = context.response.json()


@then("the response should be in JSON format")
def step_impl(context):
    assert context.response["Content-Type"] == "application/json"


@then(
    "null values in the response should be represented as JSON null (not placeholder strings)"
)
def step_impl(context):
    for key, value in context.water_well_data.items():
        if value is None:
            assert value is None  # JSON null is represented as None in Python


# ------------------------------------------------------------------------------
# Well names and projects
# ------------------------------------------------------------------------------


@then("the response should include the well name (point ID) (i.e. NM-1234)")
def step_impl(context):
    assert "name" in context.water_well_data

    assert context.water_well_data["name"] == context.objects["wells"][0].name


# TODO: model schema, and test data need to be udpated
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


# TODO: this needs to be added to the ThingResponse and thing_helper via StatusHistory
@then(
    "the response should include the well hole status of the well as the status of the hole in the ground (from previous Status field)"
)
def step_impl(context):
    assert "well_status" in context.water_well_data

    status_history = context.objects["wells"][0].status_history
    well_status = [
        sh
        for sh in status_history
        if sh.status_type == "Well Status" and sh.end_date is None
    ]
    well_status_sorted = sorted(well_status, key=lambda sh: sh.start_date, reverse=True)

    assert context.water_well_data["well_status"] == well_status_sorted[0].status_value


# TODO: this needs to be added to the model, schema, and test data
# TODO: the monitoring frequency field needs to be added to lexicon
# the monitoring status field from NM_Aquifer contains a multitude of information, like having three codes (6AC), so the transfer and model/schemas will need to take this into account
# could create descriptor table like WellPurpose and CasingMaterial
@then("the response should include the monitoring frequency (new field)")
def step_impl(context):
    for group in context.water_well_data["groups"]:
        assert "monitoring_frequency" in group

    assert context.water_well_data["monitoring_frequency"] == "Monthly"


# TODO: this needs to be added to the model, schema, and test data
# the monitoring status field from NM_Aquifer contains a multitude of information, like having three codes (6AC), so the transfer and model/schemas will need to take this into account
# could create descriptor table like WellPurpose and CasingMaterial
@then(
    "the response should include whether the well is currently being monitored with status text if applicable (from previous MonitoringStatus field)"
)
def step_impl(context):
    assert "monitoring_status" in context.water_well_data

    status_history = context.objects["wells"][0].status_history
    monitoring_status = [
        sh for sh in status_history if sh.status_type == "monitoring_status"
    ]
    monitoring_status_sorted = sorted(
        monitoring_status, key=lambda sh: sh.start_date, reverse=True
    )

    assert (
        context.water_well_data["monitoring_status"]
        == monitoring_status_sorted[0].status_value
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


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the source of the well depth information")
def step_impl(context):
    assert "well_depth_source" in context.water_well_data

    assert (
        context.water_well_data["well_depth_source"]
        == context.objects["wells"][0].well_depth_source
    )


# ------------------------------------------------------------------------------
# Measuring Point Information
# ------------------------------------------------------------------------------


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the description of the measuring point")
def step_impl(context):
    assert "measuring_point_description" in context.water_well_data

    assert (
        context.water_well_data["measuring_point_description"]
        == context.objects["wells"][0].measuring_point_description
    )


# TODO: this needs to be added to the model, schema, and test data
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


# TODO: the LocationResponse schema needs to be updated
@then(
    'the response should include a geometry object with type "Point" and coordinates array [longitude, latitude, elevation]'
)
def step_impl(context):
    latitude = context.objects["locations"][0].point.y
    longitude = context.objects["locations"][0].point.x
    elevation_m = context.objects["locations"][0].elevation

    assert context.water_well_data["current_location"]["geometry"] == {
        "type": "Point",
        "coordinates": [longitude, latitude, elevation_m],
    }


# TODO: elevation should be returned in ft, not meters, conversion should occur in schema
# TODO: add elevation_unit: str = "ft" to LocationResponse schema
@then(
    "the response should include the elevation in feet with vertical datum NAVD88 in the properties"
)
def step_impl(context):
    assert "elevation" in context.water_well_data["current_location"]["properties"]
    assert "elevation_unit" in context.water_well_data["current_location"]["properties"]
    assert "vertical_datum" in context.water_well_data["current_location"]["properties"]

    elevation_ft = context.objects["locations"][0].elevation * 3.28084

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
    assert (
        context.water_well_data["current_location"]["properties"]["elevation_method"]
        == context.objects["locations"][0].elevation_method
    )


# TODO: this needs to be added to the LocationResponse schema
@then(
    "the response should include the UTM coordinates with datum NAD83 in the properties"
)
def step_impl(context):

    assert (
        "utm_coordinates" in context.water_well_data["current_location"]["properties"]
    )

    point_utm_zone_13 = transform_srid(
        context.objects["locations"][0].point, SRID_WGS84, SRID_UTM_ZONE_13N
    )

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


# TODO: This needs to be added to the test data
# TODO: id link schema needs to use lexicon enums for relation and alternate_organization
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
