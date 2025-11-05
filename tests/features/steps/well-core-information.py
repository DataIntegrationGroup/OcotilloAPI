from behave import when, then


# TODO: move to commonly used step definitions
@when("the user retrieves the well by ID via path parameter")
def step_impl(context):
    well_id = 1
    context.water_well_response = context.client.get(f"/thing/water-well/{well_id}")
    context.water_well_data = context.water_well_response.json()


@then("the response should be in JSON format")
def step_impl(context):
    assert context.water_well_response["Content-Type"] == "application/json"


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


# TODO: this needs to be added to the model, schema, and test data
# TODO: how do we rectify this with the name field? Is there a better way to name this?
@then(
    "the response should include the site name(s) for the well (i.e. John Smith House Well)"
)
def step_impl(context):
    assert "site_name" in context.water_well_data
    assert context.water_well_data["site_name"] == "John Smith House Well"


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


# TODO: this needs to be added to the LocationResponse schema
@then(
    "the response should include the latitude and longitude in decimal degrees with datum WGS84"
)
def step_impl(context):
    data = context.response.json()
    assert (
        data["current_location"]["geographic_coordinate_system"]["latitude"]
        == 33.809665
    )
    assert (
        data["current_location"]["geographic_coordinate_system"]["longitude"]
        == -107.949533
    )
    assert (
        data["current_location"]["geographic_coordinate_system"]["horizontal_datum"]
        == "WGS84"
    )


# TODO: this needs to be added to the LocationResponse schema
@then("the response should include the UTM coordinates with datum NAD83")
def step_impl(context):
    data = context.response.json()
    assert data["current_location"]["projected_coordinate_system"]["easting"] == 623000
    assert (
        data["current_location"]["projected_coordinate_system"]["northing"] == 3745000
    )
    assert data["current_location"]["projected_coordinate_system"]["utm_zone"] == 13
    assert (
        data["current_location"]["projected_coordinate_system"]["horizontal_datum"]
        == "NAD83"
    )


# TODO: elevation should be returned in ft, not meters, conversion should occur in schema
# TODO: add elevation_unit: str = "ft" to LocationResponse schema
@then("the response should include the elevation in feet with vertical datum NAVD88")
def step_impl(context):
    assert "elevation" in context.water_well_data["current_location"]
    assert "elevation_unit" in context.water_well_data["current_location"]
    assert "vertical_datum" in context.water_well_data["current_location"]
    assert context.water_well_data["current_location"]["elevation"] == 2464.9
    assert context.water_well_data["current_location"]["elevation_unit"] == "ft"
    assert context.water_well_data["current_location"]["vertical_datum"] == "NAVD88"


@then(
    "the response should include the elevation method (i.e. interpolated from digital elevation model)"
)
def step_impl(context):
    assert "elevation_method" in context.water_well_data["current_location"]
    assert (
        context.water_well_data["current_location"]["elevation_method"]
        == "Survey-grade GPS"
    )


# ------------------------------------------------------------------------------
# Alternate Identifiers
# ------------------------------------------------------------------------------


# TODO: This needs to be added to the test data
# TODO: id link schema needs to use lexicon enums for relation and alternate_organization
@then(
    "the response should include any alternate IDs for the well like the USGS site number or the OSE well ID and OSE well tag ID"
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
