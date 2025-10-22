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


@when('the user retrieves the well "WL-0001"')
def step_impl(context):
    context.response = context.client.get("thing?name=WL-0001")


@then("the system should return a 200 status code")
def step_impl(context):
    assert context.response.status_code == 200


@then("the system should return a response in JSON format")
def step_impl(context):
    assert context.response.headers["Content-Type"] == "application/json"


@then("the response should include notes")
def step_impl(context):
    assert "notes" in context.response.json()["items"][0]


@then("the notes should be a non-empty string")
def step_impl(context):
    assert bool(context.response.json()["items"][0]) == True


# ============= EOF =============================================
