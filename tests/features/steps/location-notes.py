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


@when("the user retrieves the location with ID 1")
def step_impl(context):
    context.response = context.client.get("location/1")


@then("the response should include a current location")
def step_impl(context):
    assert context.response.json()["current_location"]


@then("the current location should include notes")
def step_impl(context):
    context.notes = context.response.json()["current_location"]["notes"]
    assert context.notes


# @then("the location should include notes")
# def step_impl(context):
#     print(context.response.json())
#     context.notes = context.response.json()["current_location"]["notes"]
#     assert context.notes


# ============= EOF =============================================
