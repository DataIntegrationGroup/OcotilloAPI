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
def step_impl(context):
    context.response = context.client.get("/thing", params={"thing_type": "water well"})


@then("the response should include at least one thing")
def step_impl(context):
    data = context.response.json()
    context.data = data["items"]
    assert len(context.data) > 0


@then('the response should only include things of type "water well"')
def step_impl(context):
    for d in context.data:
        assert d["thing_type"] == "water well"


@when('the user requests things with type "spring"')
def step_impl(context):
    context.response = context.client.get("/thing", params={"thing_type": "spring"})


@then('the response should only include things of type "spring"')
def step_impl(context):
    for d in context.data:
        assert d["thing_type"] == "spring"


# ============= EOF =============================================
