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
def step_when_the_user_retrieves_the_well_9999(context):
    context.response = context.client.get("thing/water-well/9999")
    context.notes = {}


@then("the response should include an error message indicating the well was not found")
def step_then_the_response_should_include_an_error_message_indicating_the_well(context):
    assert {"detail": "Thing with ID 9999 not found."} == context.response.json()


@then("the notes should be a non-empty string")
def step_then_the_notes_should_be_a_non_empty_string(context):
    for k, note in context.notes.items():
        assert note, f"{k} Note is empty"


@then(
    "the response should include location notes (i.e. driving directions and geographic well location notes)"
)
def step_step_step(context):
    data = context.response.json()
    location = data["current_location"]
    assert "notes" in location["properties"], "Response does not include location notes"
    assert location["properties"]["notes"] is not None, "Location notes is null"
    context.notes["location"] = location["properties"]["notes"]


@then(
    "the response should include construction notes (i.e. pump notes and other construction notes)"
)
def step_step_step_2(context):
    data = context.response.json()
    assert "construction_notes" in data, "Response does not include construction notes"
    assert data["construction_notes"] is not None, "Construction notes is null"
    context.notes["construction"] = data["construction_notes"]


@then("the response should include general well notes (catch all notes field)")
def step_then_the_response_should_include_general_well_notes_catch_all_notes(context):
    data = context.response.json()
    assert "general_notes" in data, "Response does not include notes"
    assert data["general_notes"] is not None, "Notes is null"
    context.notes["general"] = data["general_notes"]


@then(
    "the response should include sampling procedure notes (notes about sampling procedures for all sample types, like water levels and water chemistry)"
)
def step_step_step_3(context):
    data = context.response.json()
    assert (
        "sampling_procedure_notes" in data
    ), "Response does not include sampling procedure notes"
    assert (
        data["sampling_procedure_notes"] is not None
    ), "Sampling Procedure notes is null"
    context.notes["sampling_procedure"] = data["sampling_procedure_notes"]


@then(
    "the response should include water notes (i.e. water bearing zone information and other info from ose reports)"
)
def step_step_step_4(context):
    data = context.response.json()
    assert "water_notes" in data, "Response does not include water notes"
    assert data["water_notes"] is not None, "Water notes is null"
    context.notes["water"] = data["water_notes"]


# ============= EOF =============================================
