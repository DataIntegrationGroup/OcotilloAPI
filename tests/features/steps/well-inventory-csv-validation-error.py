# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================

from behave import then
from behave.runner import Context


def _handle_validation_error(context, expected_errors):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])

    def _matches(expected, actual):
        field_match = str(expected.get("field", "")) in str(actual.get("field", ""))
        error_match = str(expected.get("error", "")) in str(actual.get("error", ""))
        return field_match and error_match

    def _find_match(expected_idx: int, used_indices: set[int]) -> bool:
        if expected_idx == len(expected_errors):
            return True

        expected = expected_errors[expected_idx]
        for actual_idx, actual in enumerate(validation_errors):
            if actual_idx in used_indices or not _matches(expected, actual):
                continue
            if _find_match(expected_idx + 1, used_indices | {actual_idx}):
                return True
        return False

    assert _find_match(0, set()), (
        f"Expected at least {len(expected_errors)} distinct validation error matches for "
        f"{expected_errors}. Got: {validation_errors}"
    )


def _assert_any_validation_error_contains(
    context: Context, field_fragment: str | None, error_fragment: str
):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert validation_errors, "Expected at least one validation error"
    found = False
    for error in validation_errors:
        field = str(error.get("field", ""))
        message = str(error.get("error", ""))
        if field_fragment and field_fragment not in field:
            continue
        if error_fragment in message:
            found = True
            break
    assert (
        found
    ), f"Expected validation error containing field '{field_fragment}' and message '{error_fragment}'"


@then(
    'the response includes a validation error indicating the missing "address_type" value'
)
def step_step_step(context: Context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, All contact address fields must be provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating the invalid UTM coordinates")
def step_then_the_response_includes_a_validation_error_indicating_the_invalid_utm(
    context: Context,
):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, UTM coordinates are outside of the NM. E=457100.0 N=4159020.0 Zone=13N",
        },
        {
            "field": "composite field error",
            "error": "Value error, Invalid utm zone. Must be one of: 12N, 13N",
        },
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating an invalid "contact_type" value'
)
def step_step_step_2(context):
    expected_errors = [
        {
            "field": "contact_1_type",
            "error": "Input should be 'Primary', 'Secondary' or 'Field Event Participant'",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating the missing "email_type" value'
)
def step_step_step_3(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_email_1_type type must be provided if email is provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating the missing "phone_type" value'
)
def step_step_step_4(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_phone_1_type must be provided if phone number is provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating the missing "contact_role" field'
)
def step_step_step_5(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_role is required when contact fields are provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    "the response includes a validation error indicating the invalid postal code format"
)
def step_step_step_6(context):
    expected_errors = [
        {
            "field": "contact_1_address_1_postal_code",
            "error": "Value error, Invalid postal code",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    "the response includes a validation error indicating the invalid phone number format"
)
def step_step_step_7(context):
    expected_errors = [
        {
            "field": "contact_1_phone_1",
            "error": "Value error, Invalid phone number. 55-555-0101",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating the invalid email format")
def step_then_the_response_includes_a_validation_error_indicating_the_invalid_email(
    context,
):
    expected_errors = [
        {
            "field": "contact_1_email_1",
            "error": "Value error, Invalid email format. john.smithexample.com",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating the missing "contact_role" value'
)
def step_step_step_8(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_role is required when contact data is provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating the missing "contact_type" value'
)
def step_step_step_9(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_type is required when contact data is provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating a repeated header row")
def step_then_the_response_includes_a_validation_error_indicating_a_repeated_header(
    context: Context,
):
    expected_errors = [{"field": "header", "error": "Duplicate header row"}]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating duplicate header names")
def step_then_the_response_includes_a_validation_error_indicating_duplicate_header_names(
    context: Context,
):

    expected_errors = [
        {"field": "['contact_1_email_1']", "error": "Duplicate columns found"}
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating an invalid boolean value for the "is_open" field'
)
def step_step_step_9(context: Context):
    expected_errors = [
        {
            "field": "is_open",
            "error": "Input should be a valid boolean, unable to interpret input",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then(
    "the response includes validation errors for each missing water level entry field"
)
def step_step_step_10(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, All water level fields must be provided",
        },
        {
            "field": "composite field error",
            "error": "Value error, All water level fields must be provided",
        },
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating an invalid "address_type" value'
)
def step_then_response_includes_invalid_address_type_error(context: Context):
    _assert_any_validation_error_contains(context, "address", "Input should be")


@then("the response includes a validation error indicating an invalid state value")
def step_then_response_includes_invalid_state_error(context: Context):
    _assert_any_validation_error_contains(
        context, "state", "Value error, State must be a 2 letter abbreviation"
    )


@then(
    'the response includes a validation error indicating an invalid "well_hole_status" value'
)
def step_then_response_includes_invalid_well_hole_status_error(context: Context):
    _assert_any_validation_error_contains(
        context, "Database error", "database error occurred"
    )


@then(
    'the response includes a validation error indicating an invalid "monitoring_status" value'
)
def step_then_response_includes_invalid_monitoring_status_error(context: Context):
    _assert_any_validation_error_contains(context, "monitoring", "Input should be")


@then(
    'the response includes a validation error indicating an invalid "well_pump_type" value'
)
def step_then_response_includes_invalid_well_pump_type_error(context: Context):
    _assert_any_validation_error_contains(context, "well_pump_type", "Input should be")


@then(
    'the response includes a validation error indicating that at least one of "contact_1_name" or "contact_1_organization" must be provided'
)
@then(
    'the response includes validation errors indicating that both "contact_1_name" and "contact_1_organization" must be provided when any contact information is present'
)
def step_then_response_includes_contact_name_or_org_required_error(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert validation_errors, f"Expected validation errors, got: {response_json}"
    found = any(
        "composite field error" in str(err.get("field", ""))
        and (
            "At least one of contact_1_name or contact_1_organization must be provided"
            in str(err.get("error", ""))
        )
        for err in validation_errors
    )

    assert (
        found
    ), f"Expected contact validation error requiring contact_1_name or contact_1_organization. Got: {validation_errors}"


@then(
    'the response includes a validation error indicating that "water_level_date_time" is required when "depth_to_water_ft" is provided'
)
def step_then_response_includes_water_level_datetime_required_error(context: Context):
    _assert_any_validation_error_contains(
        context,
        "composite field error",
        "water_level_date_time is required when depth_to_water_ft is provided",
    )


# ============= EOF =============================================
