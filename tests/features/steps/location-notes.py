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


@when("the user retrieves the location by ID via path parameter")
def step_when_the_user_retrieves_the_location_by_id_via_path_parameter(context):
    location_id = context.objects["locations"][0].id
    context.response = context.client.get(f"location/{location_id}")


@then("the response should include a current location")
def step_then_the_response_should_include_a_current_location(context):
    assert context.response.json()["current_location"]


@then("the current location should include notes")
def step_then_the_current_location_should_include_notes(context):
    context.notes = context.response.json()["current_location"]["properties"]["notes"]
    assert context.notes


@then("the notes should be a list of dictionaries")
def step_then_the_notes_should_be_a_list_of_dictionaries(context):
    assert isinstance(context.notes, list)
    assert all(isinstance(n, dict) for n in context.notes)


@then('each note dictionary should have "content" and "note_type" keys')
def step_then_each_note_dictionary_should_have_content_and_note_type_keys(context):
    for note in context.notes:
        assert "content" in note
        assert "note_type" in note


@then("each note in the notes list should be a non-empty string")
def step_then_each_note_in_the_notes_list_should_be_a_non(context):
    for note in context.notes:
        assert note["content"], "Note is empty"


@then("the location response should include notes")
def step_then_the_location_response_should_include_notes(context):
    context.notes = context.response.json()["notes"]
    assert context.notes


# ============= EOF =============================================
