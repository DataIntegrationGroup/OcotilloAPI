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

    assert len(validation_errors) == len(expected_errors), "Expected 1 validation error"
    for v, e in zip(validation_errors, expected_errors):
        assert v["field"] == e["field"], f"Expected {e['field']} for {v['field']}"
        assert v["error"] == e["error"], f"Expected {e['error']} for {v['error']}"


@then(
    'the response includes a validation error indicating the missing "address_type" value'
)
def step_impl(context: Context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, All contact address fields must be provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating the invalid UTM coordinates")
def step_impl(context: Context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, UTM coordinates are outside of the NM",
        },
        {
            "field": "composite field error",
            "error": "Value error, UTM coordinates are outside of the NM",
        },
    ]
    _handle_validation_error(context, expected_errors)


@then(
    'the response includes a validation error indicating an invalid "contact_type" value'
)
def step_impl(context):
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
def step_impl(context):
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
def step_impl(context):
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
def step_impl(context):
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
def step_impl(context):
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
def step_impl(context):
    expected_errors = [
        {
            "field": "contact_1_phone_1",
            "error": "Value error, Invalid phone number. 55-555-0101",
        }
    ]
    _handle_validation_error(context, expected_errors)


@then("the response includes a validation error indicating the invalid email format")
def step_impl(context):
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
def step_impl(context):
    expected_errors = [
        {
            "field": "composite field error",
            "error": "Value error, contact_1_type must be provided if name is provided",
        }
    ]
    _handle_validation_error(context, expected_errors)


# ============= EOF =============================================
