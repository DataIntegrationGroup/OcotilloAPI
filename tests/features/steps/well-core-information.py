from behave import when, then


@when("the user retrieves the well by ID via path parameter")
def step_impl(context):
    well_id = 1
    context.response = context.client.get(f"/thing/water-well/{well_id}")


@then("the system should return a 200 status code")
def step_impl(context):
    assert context.response.status_code == 200


@then("the response should be in JSON format")
def step_impl(context):
    assert context.response.headers["Content-Type"] == "application/json"


# ------------------------------------------------------------------------------
# Well names and projects
# ------------------------------------------------------------------------------


@then("the response should include the well name (point ID) (i.e. NM-1234)")
def step_impl(context):
    data = context.response.json()
    assert data["name"] == "WL-0001"


# TODO: this needs to be added to the ThingResponse
@then("the response should include the project(s) or group(s) associated with the well")
def step_impl(context):
    data = context.response.json()
    assert data["groups"] == ["Collabnet"]


# TODO: this needs to be added to the model, schema, and test data
# TODO: how do we rectify this with the name field? Is there a better way to name this?
@then(
    "the response should include the site name(s) for the well (i.e. John Smith House Well)"
)
def step_impl(context):
    data = context.response.json()
    assert data["site_name"] == "John Smith House Well"


# ------------------------------------------------------------------------------
# Well Purpose and Status and Monitoring Status
# ------------------------------------------------------------------------------


@then("the response should include the purpose of the well (current use)")
def step_impl(context):
    data = context.response.json()
    assert sorted(data["well_purposes"]) == sorted(["Domestic", "Irrigation"])


# TODO: this needs to be added to the ThingResponse and thing_helper via StatusHistory
@then(
    "the response should include the well status of the well as the status of the hole in the ground"
)
def step_impl(context):
    data = context.response.json()
    assert data["well_status"] == "Active"


# TODO: this needs to be added to the model, schema, and test data
# TODO: the monitoring frequency field needs to be added to lexicon
@then("the response should include the monitoring frequency (new field)")
def step_impl(context):
    data = context.response.json()
    assert data["monitoring_frequency"] == "Monthly"


# TODO: this needs to be added to the model, schema, and test data
@then(
    "the response should include whether the well is currently being monitored with status text if applicable (from previous status field)"
)
def step_impl(context):
    data = context.response.json()
    assert data["is_being_monitored"] == True
    assert data["monitoring_status"] == "Active"


# ------------------------------------------------------------------------------
# Data Lifecycle and Public Visibility
# ------------------------------------------------------------------------------


@then("the response should include the release status of the well record")
def step_impl(context):
    data = context.response.json()
    assert data["release_status"] == "draft"


# ------------------------------------------------------------------------------
# Well Physical Properties
# ------------------------------------------------------------------------------


@then("the response should include the hole depth in feet")
def step_impl(context):
    data = context.response.json()
    assert data["hole_depth"] == 10


@then("the response should include the well depth in feet")
def step_impl(context):
    data = context.response.json()
    assert data["well_depth"] == 10


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the source of the well depth information")
def step_impl(context):
    data = context.response.json()
    assert data["well_depth_source"] == "Measured"


# ------------------------------------------------------------------------------
# Measuring Point Information
# ------------------------------------------------------------------------------


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the description of the measuring point")
def step_impl(context):
    data = context.response.json()
    assert data["measuring_point_description"] == "Top of Casing"


# TODO: this needs to be added to the model, schema, and test data
@then("the response should include the measuring point height in feet")
def step_impl(context):
    data = context.response.json()
    assert data["measuring_point_height"] == 4
    assert data["measuring_point_height_unit"] == "ft"


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


@then("the response should include the elevation in feet with vertical datum NAVD88")
def step_impl(context):
    data = context.response.json()
    assert data["current_location"]["elevation"] == 2464.9
    assert data["current_location"]["vertical_datum"] == "NAVD88"


@then(
    "the response should include the elevation method (i.e. interpolated from digital elevation model)"
)
def step_impl(context):
    data = context.response.json()
    assert data["current_location"]["elevation_method"] == "Survey-grade GPS"


# ------------------------------------------------------------------------------
# Alternate Identifiers
# ------------------------------------------------------------------------------


# TODO: This needs to be added to the model, schema, and test data
@then(
    "the response should include any alternate IDs for the well like the USGS site number or the OSE well ID and OSE well tag ID"
)
def step_impl(context):
    data = context.response.json()
    assert "alternate_ids" in data
    assert "usgs_site_number" in data["alternate_ids"]
    assert "ose_well_id" in data["alternate_ids"]
    assert "ose_well_tag_id" in data["alternate_ids"]
