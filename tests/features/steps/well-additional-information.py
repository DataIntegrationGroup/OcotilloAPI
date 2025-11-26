from behave import then

from services.util import retrieve_latest_polymorphic_history_table_record


# ------------------------------------------------------------------------------
# Permissions / Operational OK flags
# ------------------------------------------------------------------------------
@then(
    "the response should include whether repeat measurement permission is granted for the well"
)
def step_impl(context):
    permission_type = "Water Level Sample"
    assert "permissions" in context.water_well_data

    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", permission_type
    )

    water_well_data_permissions = [
        p
        for p in context.water_well_data["permissions"]
        if p["permission_type"] == permission_type
    ][0]
    assert (
        water_well_data_permissions["permission_type"]
        == permission_record.permission_type
    )
    assert (
        water_well_data_permissions["permission_allowed"]
        == permission_record.permission_allowed
    )
    assert water_well_data_permissions[
        "start_date"
    ] == permission_record.start_date.strftime("%Y-%m-%d")
    if permission_record.end_date:
        assert water_well_data_permissions[
            "end_date"
        ] == permission_record.end_date.strftime("%Y-%m-%d")
    else:
        assert water_well_data_permissions["end_date"] is None


@then("the response should include whether sampling permission is granted for the well")
def step_impl(context):
    permission_type = "Water Chemistry Sample"
    assert "permissions" in context.water_well_data

    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", permission_type
    )

    water_well_data_permissions = [
        p
        for p in context.water_well_data["permissions"]
        if p["permission_type"] == permission_type
    ][0]
    assert (
        water_well_data_permissions["permission_type"]
        == permission_record.permission_type
    )
    assert (
        water_well_data_permissions["permission_allowed"]
        == permission_record.permission_allowed
    )
    assert water_well_data_permissions[
        "start_date"
    ] == permission_record.start_date.strftime("%Y-%m-%d")
    if permission_record.end_date:
        assert water_well_data_permissions[
            "end_date"
        ] == permission_record.end_date.strftime("%Y-%m-%d")
    else:
        assert water_well_data_permissions["end_date"] is None


@then(
    "the response should include whether datalogger installation permission is granted for the well"
)
def step_impl(context):
    permission_type = "Datalogger Installation"
    assert "permissions" in context.water_well_data

    permission_record = retrieve_latest_polymorphic_history_table_record(
        context.objects["wells"][0], "permission_history", permission_type
    )

    water_well_data_permissions = [
        p
        for p in context.water_well_data["permissions"]
        if p["permission_type"] == permission_type
    ][0]
    assert (
        water_well_data_permissions["permission_type"]
        == permission_record.permission_type
    )
    assert (
        water_well_data_permissions["permission_allowed"]
        == permission_record.permission_allowed
    )
    assert water_well_data_permissions[
        "start_date"
    ] == permission_record.start_date.strftime("%Y-%m-%d")
    if permission_record.end_date:
        assert water_well_data_permissions[
            "end_date"
        ] == permission_record.end_date.strftime("%Y-%m-%d")
    else:
        assert water_well_data_permissions["end_date"] is None


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
    assert set(context.water_well_data["well_casing_materials"]) == {
        m.material for m in context.objects["wells"][0].well_casing_materials
    }


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


@then(
    "the response should include the formation as the formation zone of well completion"
)
def step_impl(context):
    assert "geologic_formations" in context.water_well_data
    assert context.water_well_data["geologic_formations"] == [
        context.objects["geologic_formations"][0].formation_code
    ]


@then(
    "the response should include the aquifer class code to classify the aquifer into aquifer system."
)
def step_impl(context):
    for aquifer in context.water_well_data["aquifers"]:
        assert "aquifer_system" in aquifer
    assert {a.get("aquifer_system") for a in context.water_well_data["aquifers"]} == {
        system.name for system in context.objects["aquifer_systems"]
    }


@then(
    "the response should include the aquifer type as the type of aquifers penetrated by the well"
)
def step_impl(context):
    for aquifer in context.water_well_data["aquifers"]:
        assert "aquifer_types" in aquifer

        if aquifer["aquifer_system"] == "Aquifer A":
            assert set(aquifer["aquifer_types"]) == {
                a.aquifer_type for a in context.objects["aquifer_types"]
            }
        else:
            assert aquifer["aquifer_types"] == []
