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
from behave import when, then, given
from db import Thing, TransducerObservation
from db.engine import session_ctx
from sqlalchemy import select


@given("the system has valid well and transducer data in the database")
def step_given_the_system_has_valid_well_and_transducer_data_in_the(context):
    with session_ctx() as session:
        sql = select(Thing).where(Thing.thing_type == "water well")
        wells = session.execute(sql).unique().scalars().all()
        assert len(wells) > 0, "No wells found in db"

        sql = select(TransducerObservation)
        transducer_observations = session.execute(sql).scalars().all()
        assert len(transducer_observations) > 0, "No transducer observations found db"


@when("the user requests transducer data for a non-existing well")
def step_when_the_user_requests_transducer_data_for_a_non_existing_well(context):
    context.response = context.client.get(
        "/observation/transducer-groundwater-level?thing_id=9999"
    )


@when("the user requests transducer data for a well")
def step_when_the_user_requests_transducer_data_for_a_well(context):
    context.response = context.client.get(
        f"/observation/transducer-groundwater-level?thing_id={context.objects['wells'][0].id}",
    )


@then("each page should be an array of transducer data")
def step_then_each_page_should_be_an_array_of_transducer_data(context):
    data = context.response.json()
    assert len(data["items"]) > 0, "Expected at least one transducer data entry"


@then("each transducer data entry should include a timestamp, value, status")
def step_then_each_transducer_data_entry_should_include_a_timestamp_value_status(
    context,
):
    data = context.response.json()
    items = data["items"][0]
    item = items["observation"]
    block = items["block"]

    assert "observation_datetime" in item, f"Expected a timestamp in the data {item}"
    assert "value" in item, f"Expected a value in the data {item}"
    assert "review_status" in block, f"Expected a review_status in the block {block}"

    context.timestamp = item["observation_datetime"]
    context.value = item["value"]
    context.status = block["review_status"]


@then("the timestamp should be in ISO 8601 format")
def step_then_the_timestamp_should_be_in_iso_8601_format(context):
    # assert that time stamp is in ISO 8601 format
    from datetime import datetime

    dt = datetime.fromisoformat(context.timestamp)
    assert isinstance(
        dt, datetime
    ), f"Timestamp is not in ISO 8601 format: {context.timestamp}"


@then("the value should be a numeric type")
def step_then_the_value_should_be_a_numeric_type(context):
    assert isinstance(context.value, (int, float))


@then('the status should be one of "approved", "not reviewed"')
def step_then_the_status_should_be_one_of_approved_not_reviewed(context):
    assert context.status in (
        "approved",
        "not reviewed",
    ), f'Unexpected status: {context.status} not in "approved", "not reviewed"'


# ============= EOF =============================================
