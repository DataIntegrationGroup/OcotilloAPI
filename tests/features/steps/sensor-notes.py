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
from behave import when, then
from behave.runner import Context


@when("the user requests the sensor with ID 1")
def step_impl(context: Context):
    context.response = context.client.get("sensor/1")


@when("the user requests the sensor with ID 9999")
def step_impl(context: Context):
    context.response = context.client.get("sensor/9999")


@then(
    "the response should include an error message indicating the sensor was not found"
)
def step_impl(context: Context):
    assert {"detail": "Sensor with ID 9999 not found."} == context.response.json()


# ============= EOF =============================================
