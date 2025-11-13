from behave import when, then

from services.util import retrieve_polymorphic_table_record


@when("the user retrieves the well by ID via path parameter")
def step_impl_retrieve_well_by_id(context):
    context.well = context.objects["wells"][0]
    context.response = context.client.get(f"/thing/water-well/{context.well.id}")
    context.data = context.response.json()


@then(
    "null values in the response should be represented as JSON null (not placeholder strings)"
)
def step_impl(context):
    for key, value in context.data.items():
        if value is None:
            assert value is None  # JSON null is represented as None in Python


# ------------------------------------------------------------------------------
# Permissions / Operational OK flags
# ------------------------------------------------------------------------------
@then(
    "the response should include whether repeat measurement permission is granted for the well"
)
def step_impl(context):
    assert "permissions" in context.data

    permission_record = retrieve_polymorphic_table_record(
        context.well, "permissions", "Water Level Sample", latest=True
    )

    assert (
        context.data["permissions"]["allow_water_level_samples"]
        == permission_record.permission_allowed
    )


@then("the response should include whether sampling permission is granted for the well")
def step_impl(context):
    assert "permissions" in context.data

    permission_record = retrieve_polymorphic_table_record(
        context.well, "permissions", "Water Chemistry Sample", latest=True
    )

    assert (
        context.data["permissions"]["allow_water_chemistry_samples"]
        == permission_record.permission_allowed
    )


@then(
    "the response should include whether datalogger installation permission is granted for the well"
)
def step_impl(context):
    assert "permissions" in context.data

    permission_record = retrieve_polymorphic_table_record(
        context.well, "permissions", "Datalogger Installation", latest=True
    )

    assert (
        context.data["permissions"]["allow_datalogger_installation"]
        == permission_record.permission_allowed
    )


# ------------------------------------------------------------------------------
# Well Construction Information
# ------------------------------------------------------------------------------


@then("the response should include the completion date of the well")
def step_impl(context):
    assert "well_completion_date" in context.data
    assert context.data[
        "well_completion_date"
    ] == context.well.well_completion_date.strftime("%Y-%m-%d")


# TODO: needs to be added to model, schemas, test data
@then("the response should include the source of the completion information")
def step_impl(context):
    assert "completion_info_source" in context.data
    assert context.data["completion_info_source"] == context.well.completion_info_source


@then("the response should include the driller name")
def step_impl(context):
    assert "well_driller_name" in context.data
    assert context.data["well_driller_name"] == context.well.well_driller_name


@then("the response should include the construction method")
def step_impl(context):
    assert "well_construction_method" in context.data
    assert (
        context.data["well_construction_method"]
        == context.well.well_construction_method
    )


# TODO: needs to be added to model, schemas, test data
@then("the response should include the source of the construction information")
def step_impl(context):
    assert "construction_info_source" in context.data
    assert (
        context.data["construction_info_source"]
        == context.well.construction_info_source
    )


# ------------------------------------------------------------------------------
# Additional Well Physical Properties
# ------------------------------------------------------------------------------


@then("the response should include the casing diameter in inches")
def step_impl(context):
    assert "well_casing_diameter" in context.data
    assert "well_casing_diameter_unit" in context.data

    assert context.data["well_casing_diameter"] == context.well.well_casing_diameter
    assert context.data["well_casing_diameter_unit"] == "in"


@then("the response should include the casing depth in feet below ground surface")
def step_impl(context):
    assert "well_casing_depth" in context.data
    assert "well_casing_depth_unit" in context.data

    assert context.data["well_casing_depth"] == context.well.well_casing_depth
    assert context.data["well_casing_depth_unit"] == "ft"


# TODO: needs to be added to model, schemas, test data
@then("the response should include the casing materials")
def step_impl(context):
    assert "well_casing_materials" in context.data
    assert sorted(context.data["well_casing_materials"]) == sorted(
        [m.material for m in context.well.well_casing_materials]
    )


@then("the response should include the well pump type (previously well_type field)")
def step_impl(context):
    assert "well_pump_type" in context.data
    assert context.data["well_pump_type"] == context.well.well_pump_type


@then("the response should include the well pump depth in feet (new field)")
def step_impl(context):
    assert "well_pump_depth" in context.data
    assert "well_pump_depth_unit" in context.data

    assert context.data["well_pump_depth"] == context.well.well_pump_depth
    assert context.data["well_pump_depth_unit"] == "ft"


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
    assert "formation" in context.data
    assert context.data["formation"] == context.well.formation


# TODO: needs to be added to model, schemas, test data, lexicon
@then(
    "the response should include the aquifer class code to classify the aquifer into aquifer system."
)
def step_impl(context):
    assert "aquifer_class_code" in context.data
    assert context.data["aquifer_class_code"] == context.well.aquifer_class_code


# TODO: needs to be added to model, schemas, test data
# TODO: should this be plural? that is, a descriptor model of the well
@then(
    "the response should include the aquifer type as the type of aquifers penetrated by the well"
)
def step_impl(context):
    assert "aquifer_type" in context.data
    assert context.data["aquifer_type"] == context.well.aquifer_type
