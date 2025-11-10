"""
Step Definitions for retrieving deployments and associated sensors by well name.

Feature Reference:
  File: features/well_management/retrieve_deployments.feature
  Requirement: REQ-WELL-001
  Jira: JIRA-1234

Purpose:
  Defines Given/When/Then steps for retrieving deployments and sensor data.
  These steps can be reused across similar retrieval or lookup features.

Dependencies:
  - Behave (BDD Framework)
  - requests or internal API client for data retrieval
  - pandas or tabulate for structured table validation (optional)
"""

from behave import given, when, then
from behave.runner import Context
from hamcrest import assert_that, equal_to, is_, contains_string

# -----------------------------------------------------------------------------
# Background Steps
# -----------------------------------------------------------------------------


@given("the system has valid well and deployment data in the database")
def step_impl_valid_data(context: Context):
    """
    Precondition: The test data setup should insert or mock wells, deployments, and sensors.
    In real tests, this might connect to a test DB, fixture, or stub API.
    """
    context.database = {
        "Well-Alpha": [
            {"deployment_id": "D001", "sensor_id": "S001", "sensor_type": "Pressure"},
            {
                "deployment_id": "D001",
                "sensor_id": "S002",
                "sensor_type": "Temperature",
            },
            {"deployment_id": "D002", "sensor_id": "S003", "sensor_type": "Flow Rate"},
        ],
        "Well-Beta": [
            {"deployment_id": "D010", "sensor_id": None, "sensor_type": None},
        ],
    }
    context.api_connected = True


@given("the user is authenticated as a field technician")
def step_impl_authenticated_user(context: Context):
    """Simulates user authentication."""
    context.user_role = "field_technician"
    assert context.user_role == "field_technician"


@given("the system is connected to the data service")
def step_impl_api_connection(context: Context):
    """Simulate checking connectivity to backend data service."""
    assert context.api_connected is True


# -----------------------------------------------------------------------------
# Scenario: Positive Path
# -----------------------------------------------------------------------------


@given('a well named "{well_name}" exists with deployments')
def step_impl_well_with_deployments(context: Context, well_name: str):
    """Stores deployment and sensor info from the table provided in the feature."""
    context.well_name = well_name
    context.expected_table = [row.as_dict() for row in context.table]
    context.database[well_name] = context.expected_table


@when('the technician retrieves deployments for the well "{well_name}"')
def step_impl_retrieve_deployments(context: Context, well_name: str):
    """
    Action: Retrieve all deployments and associated sensors for a given well.
    Replace this logic with actual service/API calls.
    """
    context.well_name = well_name
    context.result = context.database.get(well_name)
    if context.result is None:
        context.error_message = "Well not found"
    elif all(not row.get("sensor_id") for row in context.result):
        context.warning_message = "No sensors associated with this well"


@then(
    "the system should return a table containing all deployments and sensors for that well"
)
def step_impl_validate_table_returned(context: Context):
    """Verifies that the returned data matches expected table values."""
    assert context.result is not None, "No results returned for existing well"
    for expected_row in context.expected_table:
        assert expected_row in context.result, f"Missing row: {expected_row}"


@then("the response should include {sensor_count:d} sensors")
def step_impl_sensor_count(context: Context, sensor_count: int):
    """Asserts total number of sensors in response."""
    actual_count = sum(1 for row in context.result if row["sensor_id"])
    assert_that(actual_count, equal_to(sensor_count))


@then('the table should display columns: "{col1}", "{col2}", "{col3}"')
def step_impl_validate_columns(context: Context, col1: str, col2: str, col3: str):
    """Checks that expected table headers exist."""
    expected_columns = [col1, col2, col3]
    actual_columns = list(context.result[0].keys()) if context.result else []
    assert_that(set(actual_columns), is_(set(expected_columns)))


# -----------------------------------------------------------------------------
# Scenario: Edge Case – Well with no sensors
# -----------------------------------------------------------------------------


@given('a well named "{well_name}" exists with deployments but no sensors')
def step_impl_well_no_sensors(context: Context, well_name: str):
    """Sets up a well with deployments that have no sensors."""
    context.database[well_name] = [row.as_dict() for row in context.table]


@then("the system should return a table with deployment rows but no sensor details")
def step_impl_validate_no_sensors(context: Context):
    """Validates that table rows exist but contain no sensor data."""
    assert context.result, "Expected deployments table but got no data"
    for row in context.result:
        assert row.get("sensor_id") in (None, "", " "), "Expected no sensor_id"
        assert row.get("sensor_type") in (None, "", " "), "Expected no sensor_type"


@then('a message "No sensors associated with this well" should be displayed')
def step_impl_warning_message(context: Context):
    """Checks that a warning message is displayed."""
    assert_that(
        context.warning_message, equal_to("No sensors associated with this well")
    )


# -----------------------------------------------------------------------------
# Scenario: Negative Path – Non-existent well
# -----------------------------------------------------------------------------


@given('no well exists named "{well_name}"')
def step_impl_no_well_exists(context: Context, well_name: str):
    """Ensures the well does not exist in the database."""
    if well_name in context.database:
        del context.database[well_name]


@then('the system should display an error message "{error_msg}"')
def step_impl_error_message(context: Context, error_msg: str):
    """Validates correct error message is returned."""
    assert_that(context.error_message, contains_string(error_msg))


@then("the response table should be empty")
def step_impl_empty_response(context: Context):
    """Ensures no data is returned."""
    assert_that(context.result, is_(None))


# -----------------------------------------------------------------------------
# Scenario Outline: Validation
# -----------------------------------------------------------------------------


@given("the technician provides a well name {well_name}")
def step_impl_provide_well_name(context: Context, well_name: str):
    """Sets input well name; may be blank, numeric, or invalid."""
    context.input_well_name = (
        None
        if well_name == "NULL"
        else well_name.strip() if isinstance(well_name, str) else well_name
    )


@when("the technician requests the deployments list")
def step_impl_request_deployments_list(context: Context):
    """Simulates sending a retrieval request and handling validation errors."""
    well_name = context.input_well_name
    print(f"Retrieving deployments for well '{well_name}: {type(well_name)}'")
    try:
        float(well_name)
        context.validation_error = "Well name must be text value"
    except (ValueError, TypeError):

        if not well_name:
            context.validation_error = (
                "Well name cannot be empty"
                if well_name == ""
                else "Invalid well name input"
            )
        else:
            if well_name not in context.database:
                context.validation_error = "Well not found"
            else:
                context.result = context.database.get(well_name)


@then("the system should {expected_result}")
def step_impl_expected_result(context: Context, expected_result: str):
    """
    Checks system response based on expected outcome.
    Note: This step relies on substring matching to allow natural-language reuse.
    """
    if "error" in expected_result:
        print(expected_result.split("error")[1].strip(), context.validation_error)
        assert (
            context.validation_error
            and expected_result.split("error")[1].strip() in context.validation_error
        )
    elif "return" in expected_result:
        assert (
            context.result is not None
        ), f"Expected data for valid well name, got {context.result}"
