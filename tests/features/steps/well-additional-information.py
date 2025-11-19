from behave import then

from services.util import retrieve_latest_polymorphic_history_table_record


# ------------------------------------------------------------------------------
# Permissions / Operational OK flags
# ------------------------------------------------------------------------------
@then(
    "the response should include whether repeat measurement permission is granted for the well"
)
def step_impl(context):
    assert "allow_water_level_samples" in context.water_well_data
    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", "Water Level Sample"
    )
    assert (
        context.water_well_data["allow_water_level_samples"]
        == permission_record.permission_allowed
    )


@then("the response should include whether sampling permission is granted for the well")
def step_impl(context):
    assert "allow_water_chemistry_samples" in context.water_well_data

    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", "Water Chemistry Sample"
    )

    assert (
        context.water_well_data["allow_water_chemistry_samples"]
        == permission_record.permission_allowed
    )


@then(
    "the response should include whether datalogger installation permission is granted for the well"
)
def step_impl(context):
    assert "allow_datalogger_installation" in context.water_well_data

    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", "Datalogger Installation"
    )

    assert (
        context.water_well_data["allow_datalogger_installation"]
        == permission_record.permission_allowed
    )


# ------------------------------------------------------------------------------
# Well Construction Information
# ------------------------------------------------------------------------------


@then("the response should include the completion date of the well")
def step_impl(context):
    assert "well_completion_date" in context.water_well_data
    assert context.water_well_data["well_completion_date"] == context.objects["wells"][
        0
    ].well_completion_date.strftime("%Y-%m-%d")


@then("the response should include the source of the completion information")
def step_impl(context):
    assert "well_completion_date_source" in context.water_well_data

    assert (
        context.water_well_data["well_completion_date_source"]
        == context.objects["wells"][0].well_completion_date_source
    )


@then("the response should include the driller name")
def step_impl(context):
    assert "well_driller_name" in context.water_well_data
    assert (
        context.water_well_data["well_driller_name"]
        == context.objects["wells"][0].well_driller_name
    )


@then("the response should include the construction method")
def step_impl(context):
    assert "well_construction_method" in context.water_well_data
    assert (
        context.water_well_data["well_construction_method"]
        == context.objects["wells"][0].well_construction_method
    )


@then("the response should include the source of the construction information")
def step_impl(context):
    assert "well_construction_method_source" in context.water_well_data
    assert (
        context.water_well_data["well_construction_method_source"]
        == context.objects["wells"][0].well_construction_method_source
    )


# ------------------------------------------------------------------------------
# Additional Well Physical Properties
# ------------------------------------------------------------------------------


@then("the response should include the casing diameter in inches")
def step_impl(context):
    assert "well_casing_diameter" in context.water_well_data
    assert "well_casing_diameter_unit" in context.water_well_data

    assert (
        context.water_well_data["well_casing_diameter"]
        == context.objects["wells"][0].well_casing_diameter
    )
    assert context.water_well_data["well_casing_diameter_unit"] == "in"


@then("the response should include the casing depth in feet below ground surface")
def step_impl(context):
    assert "well_casing_depth" in context.water_well_data
    assert "well_casing_depth_unit" in context.water_well_data

    assert (
        context.water_well_data["well_casing_depth"]
        == context.objects["wells"][0].well_casing_depth
    )
    assert context.water_well_data["well_casing_depth_unit"] == "ft"


@then("the response should include the casing materials")
def step_impl(context):
    assert "well_casing_materials" in context.water_well_data
    assert sorted(context.water_well_data["well_casing_materials"]) == sorted(
        [m.material for m in context.objects["wells"][0].well_casing_materials]
    )


@then("the response should include the well pump type (previously well_type field)")
def step_impl(context):
    assert "well_pump_type" in context.water_well_data
    assert (
        context.water_well_data["well_pump_type"]
        == context.objects["wells"][0].well_pump_type
    )


@then("the response should include the well pump depth in feet (new field)")
def step_impl(context):
    assert "well_pump_depth" in context.water_well_data
    assert "well_pump_depth_unit" in context.water_well_data

    assert (
        context.water_well_data["well_pump_depth"]
        == context.objects["wells"][0].well_pump_depth
    )
    assert context.water_well_data["well_pump_depth_unit"] == "ft"


@then(
    "the response should include whether the well is open and suitable for a datalogger"
)
def step_impl(context):
    assert "is_suitable_for_datalogger" in context.water_well_data
    assert (
        context.water_well_data["is_suitable_for_datalogger"]
        == context.objects["wells"][0].is_suitable_for_datalogger
    )


# ------------------------------------------------------------------------------
# Aquifer/ Geology Information
# ------------------------------------------------------------------------------


# TODO: needs to be added to model, schemas, test data
@then(
    "the response should include the formation as the formation zone of well completion"
)
def step_impl(context):
    assert "formation" in context.water_well_data
    assert context.water_well_data["formation"] == context.objects["wells"][0].formation


# TODO: needs to be added to model, schemas, test data, lexicon
@then(
    "the response should include the aquifer class code to classify the aquifer into aquifer system."
)
def step_impl(context):
    assert "aquifer_class_code" in context.water_well_data
    assert (
        context.water_well_data["aquifer_class_code"]
        == context.objects["wells"][0].aquifer_class_code
    )


# TODO: needs to be added to model, schemas, test data
# TODO: should this be plural? that is, a descriptor model of the well
@then(
    "the response should include the aquifer type as the type of aquifers penetrated by the well"
)
def step_impl(context):
    assert "aquifer_type" in context.water_well_data
    assert (
        context.water_well_data["aquifer_type"]
        == context.objects["wells"][0].aquifer_type
    )
