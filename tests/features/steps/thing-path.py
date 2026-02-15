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


@when('the user requests things with type "water well"')
def step_when_the_user_requests_things_with_type_water_well(context):
    context.response = context.client.get("/thing/water-well")


@then("the response should include at least one thing")
def step_then_the_response_should_include_at_least_one_thing(context):
    data = context.response.json()
    context.data = data["items"]
    assert len(context.data) > 0


@then('the response should only include things of type "water well"')
def step_then_the_response_should_only_include_things_of_type_water_well(context):
    for d in context.data:
        assert d["thing_type"] == "water well"


@when('the user requests things with type "spring"')
def step_when_the_user_requests_things_with_type_spring(context):
    context.response = context.client.get("/thing/spring")


@then('the response should only include things of type "spring"')
def step_then_the_response_should_only_include_things_of_type_spring(context):
    for d in context.data:
        assert d["thing_type"] == "spring"


# ============= EOF =============================================
