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
from behave import then, given, when
from behave.runner import Context
from datetime import datetime, timedelta
from starlette.testclient import TestClient

from core.dependencies import (
    viewer_function,
    amp_viewer_function,
    amp_editor_function,
    admin_function,
    amp_admin_function,
)
from core.initializers import register_routes
from services.util import convert_dt_tz_naive_to_tz_aware


@given("a functioning api")
def step_given_api_is_running(context):
    """
    Ensures the API app is initialized and client is ready.
    Behave will keep 'context' across steps, allowing us to reuse response data.
    """
    from core.app import app

    register_routes(app)

    def override_authentication(default=True):
        """
        Override the authentication dependency for testing purposes.
        This allows all users to be considered authenticated.
        """

        def closure():
            # print("Overriding authentication")
            return default

        return closure

    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    app.dependency_overrides[viewer_function] = override_authentication()

    client = TestClient(app)
    context.client = client
    assert context.client is not None, "TestClient failed to initialize"


@when("the user retrieves the well by ID via path parameter")
def step_impl(context):
    context.response = context.client.get(
        f"thing/water-well/{context.objects['wells'][0].id}"
    )
    context.water_well_data = context.response.json()
    context.notes = {}


@then(
    "null values in the response should be represented as JSON null (not placeholder strings)"
)
def step_impl(context):
    data = context.response.json()
    for k, v in data.items():
        if v == "":
            assert v is None, f"Value for key {k} is an empty string but should be null"


@then("I should receive a successful response")
def step_impl(context):
    assert (
        context.response.status_code == 200
    ), f"Unexpected response: {context.response.text}"


@then("the system returns a 201 Created status code")
def step_impl(context):
    assert context.response.status_code == 201, (
        f"Unexpected response status code "
        f"{context.response.status_code}. "
        f"Response json: {context.response.json()}"
    )


@then("the system should return a 200 status code")
def step_impl(context):
    assert (
        context.response.status_code == 200
    ), f"Unexpected response status code {context.response.status_code}"


@then("the system should return a 404 status code")
def step_impl(context):
    assert (
        context.response.status_code == 404
    ), f"Unexpected response status code {context.response.status_code}"


@then("the system returns a 400 status code")
def step_impl(context):
    assert (
        context.response.status_code == 400
    ), f"Unexpected response status code {context.response.status_code}"


@then("the system returns a 422 Unprocessable Entity status code")
def step_impl(context):
    assert (
        context.response.status_code == 422
    ), f"Unexpected response status code {context.response.status_code}"


@then("the response should be paginated")
def step_impl(context):
    data = context.response.json()
    assert "items" in data, "Response is not paginated"
    assert "total" in data, "Response is not paginated"
    assert "page" in data, "Response is not paginated"
    assert "size" in data, "Response is not paginated"


@then("the system should return a response in JSON format")
def step_impl(context):
    assert (
        context.response.headers["Content-Type"] == "application/json"
    ), f"Unexpected response type {context.response.headers['Content-Type']}"


@then("the items should be an empty list")
def step_impl(context):
    data = context.response.json()
    assert len(data["items"]) == 0, f'Unexpected items {data["items"]}'
    assert data["total"] == 0, f'Unexpected total {data["total"]}'
    assert data["page"] == 1, f'Unexpected page {data["page"]}'


@given("the CSV includes required fields:")
def step_impl_csv_includes_required_fields(context: Context):
    """Sets up the CSV file with multiple rows of well inventory data."""
    context.required_fields = [row[0] for row in context.table]
    keys = context.rows[0].keys()
    for field in context.required_fields:
        assert field in keys, f"Missing required field: {field}"


@given("the CSV includes optional fields when available:")
def step_impl(context: Context):
    optional_fields = [row[0] for row in context.table]
    keys = context.rows[0].keys()

    for key in keys:
        if key not in context.required_fields:
            assert key in optional_fields, f"Unexpected field found: {key}"


@then(
    "all datetime objects are assigned the correct Mountain Time timezone offset based on the date value."
)
def step_impl(context: Context):
    """
    In the @given steps that prececeed this step, a list of datetime fields
    needs to be added to the context object so that they can be checked here. This way
    we can test datetime fields with different names, such as 'date_time' in well-inventory-csv
    and `water_level_date_time` in water-level-csv.
    """

    for i, row in enumerate(context.rows):

        for datetime_field in context.datetime_fields:
            # Convert date_time field
            date_time_naive = datetime.fromisoformat(row[datetime_field])
            print(date_time_naive)
            date_time_aware = convert_dt_tz_naive_to_tz_aware(
                date_time_naive, "America/Denver"
            )
            row[datetime_field] = date_time_aware.isoformat()
            # confirm correct time zone and offset
            if date_time_aware.dst() == timedelta(0):
                # MST, offset -07:00
                assert date_time_aware.utcoffset() == timedelta(
                    hours=-7
                ), "date_time offset is not -07:00"
            else:
                # MDT, offset -06:00
                assert date_time_aware.utcoffset() == timedelta(
                    hours=-6
                ), "date_time offset is not -06:00"

            # confirm the time was not changed from what was provided
            assert (
                date_time_aware.replace(tzinfo=None) == date_time_naive
            ), "date_time value was changed during timezone assignment"


# ============= EOF =============================================
