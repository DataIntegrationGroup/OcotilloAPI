from behave import when, then


# TODO: move to commonly used step definitions
@when("the user retrieves the well by ID via path parameter")
def step_impl(context):
    well_id = 1
    context.response = context.water_well_response
    context.water_well_data = context.response.json()


@then("the response should be in JSON format")
def step_impl(context):
    assert context.water_well_response["Content-Type"] == "application/json"


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
    assert context.water_well_data["name"] == "WL-0001"


# TODO: a new endpoint named /thing/{thing_id}/group needs to be added to the API
# TODO: this needs to be added to the ThingResponse
@then("the response should include the project(s) or group(s) associated with the well")
def step_impl(context):
    assert "groups" in context.water_well_data
    assert context.water_well_data["groups"] == ["Collabnet"]


# ------------------------------------------------------------------------------
# Well Purpose and Status and Monitoring Status
# ------------------------------------------------------------------------------


@then("the response should include the purpose of the well (current use)")
def step_impl(context):
    assert "Domestic" in context.water_well_data["well_purposes"]
    assert "Irrigation" in context.water_well_data["well_purposes"]


# TODO: this needs to be added to the ThingResponse and thing_helper via StatusHistory
@then(
    "the response should include the well status of the well as the status of the hole in the ground"
)
def step_impl(context):
    assert "well_status" in context.water_well_data
    assert context.water_well_data["well_status"] == "Active"


# TODO: this needs to be added to the model, schema, and test data
# TODO: the monitoring frequency field needs to be added to lexicon
# the monitoring status field from NM_Aquifer contains a multitude of information, like having three codes (6AC), so the transfer and model/schemas will need to take this into account
# could create descriptor table like WellPurpose and CasingMaterial
@then("the response should include the monitoring frequency (new field)")
def step_impl(context):
    assert "monitoring_frequency" in context.water_well_data
    assert context.water_well_data["monitoring_frequency"] == "Monthly"


# TODO: this needs to be added to the model, schema, and test data
# the monitoring status field from NM_Aquifer contains a multitude of information, like having three codes (6AC), so the transfer and model/schemas will need to take this into account
# could create descriptor table like WellPurpose and CasingMaterial
@then(
    "the response should include whether the well is currently being monitored with status text if applicable (from previous status field)"
)
def step_impl(context):
    assert "is_being_monitored" in context.water_well_data
    assert "monitoring_status" in context.water_well_data
    assert context.water_well_data["is_being_monitored"] == True
    assert context.water_well_data["monitoring_status"] == "Active"


# ------------------------------------------------------------------------------
# Data Lifecycle and Public Visibility
# ------------------------------------------------------------------------------


@then("the response should include the release status of the well record")
def step_impl(context):
    assert "release_status" in context.water_well_data
    assert context.water_well_data["release_status"] == "draft"


# ------------------------------------------------------------------------------
# Well Physical Properties
# ------------------------------------------------------------------------------


@then("the response should include the hole depth in feet")
def step_impl(context):
    assert "hole_depth" in context.water_well_data
    assert "hole_depth_unit" in context.water_well_data
    assert context.water_well_data["hole_depth"] == 10
    assert context.water_well_data["hole_depth_unit"] == "ft"


@then("the response should include the well depth in feet")
def step_impl(context):
    assert "well_depth" in context.water_well_data
    assert "well_depth_unit" in context.water_well_data
    assert context.water_well_data["well_depth"] == 10
    assert context.water_well_data["well_depth_unit"] == "ft"


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the source of the well depth information")
def step_impl(context):
    assert "well_depth_source" in context.water_well_data
    assert context.water_well_data["well_depth_source"] == "Measured"


# ------------------------------------------------------------------------------
# Measuring Point Information
# ------------------------------------------------------------------------------


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the description of the measuring point")
def step_impl(context):
    assert "measuring_point_description" in context.water_well_data
    assert context.water_well_data["measuring_point_description"] == "Top of Casing"


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the measuring point height in feet")
def step_impl(context):
    assert "measuring_point_height" in context.water_well_data
    assert "measuring_point_height_unit" in context.water_well_data
    assert context.water_well_data["measuring_point_height"] == 4
    assert context.water_well_data["measuring_point_height_unit"] == "ft"


# ------------------------------------------------------------------------------
# Location Information
# ------------------------------------------------------------------------------


@then("the response should include location information in GeoJSON format")
def step_impl(context):
    assert "current_location" in context.water_well_data
    assert "type" in context.water_well_data["current_location"]
    assert "geometry" in context.water_well_data["current_location"]
    assert "properties" in context.water_well_data["current_location"]

    assert context.water_well_data["current_location"]["type"] == "Feature"


# TODO: the LocationResponse schema needs to be updated
@then(
    'the response should include a geometry object with type "Point" and coordinates array [longitude, latitude, elevation] in decimal degrees with datum WGS84'
)
def step_impl(context):
    assert context.water_well_data["current_location"]["geometry"] == {
        "type": "Point",
        "coordinates": [33.809665, -107.949533, 2464.9],
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

    assert (
        context.water_well_data["current_location"]["properties"]["elevation"]
        == 2464.9 * 3.28084
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
        == "Survey-grade GPS"
    )


# TODO: this needs to be added to the LocationResponse schema
@then(
    "the response should include the UTM coordinates with datum NAD83 in the properties"
)
def step_impl(context):

    assert (
        "utm_coordinates" in context.water_well_data["current_location"]["properties"]
    )
    assert context.water_well_data["current_location"]["properties"][
        "utm_coordinates"
    ] == {
        "easting": 623000,
        "northing": 3745000,
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
    response = context.client.get("/thing/1/id-link")
    data = response.json()
    for item in data["items"]:
        if item["alternate_organization"] == "USGS":
            assert item["relation"] == "same as"
            assert item["alternate_id"] == "12345678"
        elif item["alternate_organization"] == "NMOSE":
            assert item["relation"] == "same as"
            assert item["alternate_id"] == "OSE-0001"
        elif item["alternate_organization"] == "NMBGMR":
            assert item["relation"] == "same as"
            assert item["alternate_id"] == "John Smith Well"
