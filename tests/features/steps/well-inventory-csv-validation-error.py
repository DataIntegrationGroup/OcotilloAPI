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
    assert len(validation_errors) == len(
        expected_errors
    ), f"Expected {len(expected_errors)} validation errors, got {len(validation_errors)}"
    for v, e in zip(validation_errors, expected_errors):
        assert v["field"] == e["field"], f"Expected {e['field']} for {v['field']}"
        assert v["error"] == e["error"], f"Expected {e['error']} for {v['error']}"
        if "value" in e:
            assert v["value"] == e["value"], f"Expected {e['value']} for {v['value']}"


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
            "error": "Value error, contact_1_role must be provided if name is provided",
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
    'the response includes a validation error indicating the missing "contact_type" value'
)
def step_step_step_8(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_type must be provided if name is provided",
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


# ============= EOF =============================================
