from behave import when, then


@when("the user retrieves the well by ID via path parameter")
def step_impl_retrieve_well_by_id(context):
    well_id = 1
    context.response = context.client.get(f"/thing/water-well/{well_id}")


# ------------------------------------------------------------------------------
# Permissions / Operational OK flags
# ------------------------------------------------------------------------------
# TODO: the API needs to be updated to include Permissions
# TODO: the schema and test data need to be updated
# TODO: should the testing data and tests contain multiple permissions, one that has expired?


@then(
    "the response should include whether repeat measurement permission is granted for the well"
)
def step_impl(context):
    data = context.response.json()
    assert data["permissions"][0]["allow_repeat_sampling"] is True


@then("the response should include whether sampling permission is granted for the well")
def step_impl(context):
    data = context.response.json()
    assert data["permissions"][0]["allow_sampling"] is True


# TODO: should this be datalogger specific?
@then(
    "the response should include whether datalogger installation permission is granted for the well"
)
def step_impl(context):
    data = context.response.json()
    assert data["permissions"][0]["allow_installation"] is True


# ------------------------------------------------------------------------------
# Well Construction Information
# ------------------------------------------------------------------------------


# TODO: needs to be added to model, schemas, test data
@then("the response should include the completion date of the well")
def step_impl(context):
    data = context.response.json()
    assert data["completion_date"] == "2020-05-15"


# TODO: needs to be added to model, schemas, test data
@then("the response should include the source of the completion information")
def step_impl(context):
    data = context.response.json()
    assert data["completion_info_source"] == "Driller Report"


# TODO: needs to be added to model, schemas, test data
@then("the response should include the driller name")
def step_impl(context):
    data = context.response.json()
    assert data["driller_name"] == "John Doe"


# TODO: needs to be added to model, schemas, test data
# TODO: needs to be an enum and added to lexicon
@then("the response should include the construction method")
def step_impl(context):
    data = context.response.json()
    assert data["construction_method"] == "Rotary Drilling"


# TODO: needs to be added to model, schemas, test data
@then("the response should include the source of the construction information")
def step_impl(context):
    data = context.response.json()
    assert data["construction_info_source"] == "Driller Report"


# ------------------------------------------------------------------------------
# Additional Well Physical Properties
# ------------------------------------------------------------------------------


# TODO: the transfer script needs to convert ft to in
@then("the response should include the casing diameter in inches")
def step_impl(context):
    data = context.response.json()
    assert data["casing_diameter"] == 10
    assert data["casing_diameter_unit"] == "in"


@then("the response should include the casing depth in feet below ground surface")
def step_impl(context):
    data = context.response.json()
    assert data["well_casing_depth"] == 30
    assert data["well_casing_depth_unit"] == "ft"


# TODO: needs to be added to model, schemas, test data
@then(
    "the response should include the casing description (previously casing notes field)"
)
def step_impl(context):
    data = context.response.json()
    assert data["well_casing_description"] == "test description"


# TODO: needs to be added to model, schemas, test data
# TODO: needs to be added to lexicon and an enum should be created
@then("the response should include the well pump type (previously well_type field)")
def step_impl(context):
    data = context.response.json()
    assert data["well_pump_type"] == "Submersible"


# TODO: needs to be added to model, schemas, test data
@then("the response should include the well pump depth in feet (new field)")
def step_impl(context):
    data = context.response.json()
    assert data["well_pump_depth"] == 100
    assert data["well_pump_depth_unit"] == "ft"


# TODO: needs to be added to model, schemas, test data
@then(
    "the response should include whether the well is open and suitable for a datalogger"
)
def step_impl(context):
    data = context.response.json()
    assert data["well_open"] is True
    assert data["well_suitable_for_datalogger"] is True


# ------------------------------------------------------------------------------
# Aquifer/ Geology Information
# ------------------------------------------------------------------------------


# TODO: needs to be added to model, schemas, test data
@then(
    "the response should include the formation as the formation zone of well completion"
)
def step_impl(context):
    data = context.response.json()
    assert data["formation"] == "Sandstone"


# TODO: needs to be added to model, schemas, test data
@then(
    "the response should include the aquifer class code to classify the aquifer into aquifer system."
)
def step_impl(context):
    data = context.response.json()
    assert data["aquifer_class_code"] == "A1"


# TODO: needs to be added to model, schemas, test data
# TODO: should this be plural? that is, a descriptor model of the well
@then(
    "the response should include the aquifer type as the type of aquifers penetrated by the well"
)
def step_impl(context):
    data = context.response.json()
    assert data["aquifer_type"] == "Confined"
