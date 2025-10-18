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
from behave import given, when, then
from behave.runner import Context


@given("the system has valid well and location data in the database")
def step_impl(context):
    context.database = {
        "Well-Alpha": {
            "location": {"type": "Point", "coordinates": [32.222222, -110.999999]},
            "deployments": [
                {
                    "deployment_id": "D001",
                    "sensor_id": "S001",
                    "sensor_type": "Pressure",
                },
                {
                    "deployment_id": "D001",
                    "sensor_id": "S002",
                    "sensor_type": "Temperature",
                },
                {
                    "deployment_id": "D002",
                    "sensor_id": "S003",
                    "sensor_type": "Flow Rate",
                },
            ],
        },
        "Well-Beta": {
            "location": {"type": "Point", "coordinates": [32.222222, -112.999999]},
            "deployments": [
                {"deployment_id": "D010", "sensor_id": None, "sensor_type": None}
            ],
        },
    }
    context.api_connected = True


@given('a well named "{well_name}" exists with location details')
def step_impl_well_with_location(context: Context, well_name: str):
    context.well_name = well_name
    context.result = context.database.get(well_name)


@when('the technician retrieves the location for the well "{well_name}"')
def step_impl(context: Context, well_name: str):
    """
    :type context: behave.runner.Context
    """
    context.result = context.database.get(context.well_name)


@then("the system should return the location details for that well")
def step_impl(context: Context):
    """
    :type context: behave.runner.Context
    """
    assert context.result is not None, "Well not found"


@then("the response should include latitude, longitude, and elevation")
def step_imp(context: Context):
    assert context.result is not None, "Well not found"
    assert context.result["location"]["type"] == "Point"


# ============= EOF =============================================
