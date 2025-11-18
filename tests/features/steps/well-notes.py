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


@when("the user retrieves the well 9999")
def step_impl(context):
    context.response = context.client.get("thing/water-well/9999")
    context.notes = {}


@then("the response should include an error message indicating the well was not found")
def step_impl(context):
    assert {"detail": "Thing with ID 9999 not found."} == context.response.json()


@then("the notes should be a non-empty string")
def step_impl(context):
    for k, note in context.notes.items():
        assert note, f"{k} Note is empty"


@then(
    "the response should include location notes (i.e. driving directions and geographic well location notes)"
)
def step_impl(context):
    data = context.response.json()
    location = data["current_location"]
    assert "notes" in location["properties"], "Response does not include location notes"
    assert location["properties"]["notes"] is not None, "Location notes is null"
    context.notes["location"] = location["properties"]["notes"]


@then(
    "the response should include construction notes (i.e. pump notes and other construction notes)"
)
def step_impl(context):
    data = context.response.json()
    assert (
        "well_construction_notes" in data
    ), "Response does not include construction notes"
    assert data["well_construction_notes"] is not None, "Construction notes is null"
    context.notes["construction"] = data["well_construction_notes"]


@then("the response should include general well notes (catch all notes field)")
def step_impl(context):
    data = context.response.json()
    assert "notes" in data, "Response does not include notes"
    assert data["notes"] is not None, "Notes is null"
    context.notes["general"] = data["notes"]


@then(
    "the response should include measuring notes (notes about measuring/visiting the well, on Access form)"
)
def step_impl(context):
    data = context.response.json()
    assert "measuring_notes" in data, "Response does not include measuring notes"
    assert data["measuring_notes"] is not None, "Measuring notes is null"
    context.notes["measuring"] = data["measuring_notes"]


@then(
    "the response should include water notes (i.e. water bearing zone information and other info from ose reports)"
)
def step_impl(context):
    data = context.response.json()
    assert "water_notes" in data, "Response does not include water notes"
    assert data["water_notes"] is not None, "Water notes is null"
    context.notes["water"] = data["water_notes"]


# ============= EOF =============================================
