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


# ================================================================================
# Uploading a valid water level entry CSV containing required and optional fields
# ================================================================================
@given("a valid CSV file for bulk water level entry upload")
def step_impl(context: Context):
    context.csv_file = "tests/features/data/water-levels-valid.csv"


@given("my CSV file is encoded in UTF-8 and uses commas as separators")
def step_impl(context: Context):
    pass


@given("my CSV file contains multiple rows of water level entry data")
def step_impl(context: Context):
    pass


@given("the CSV includes required fields:")
def step_impl(context: Context):
    pass


@given('each "well_name_point_id" value matches an existing well')
def step_impl(context: Context):
    pass


@given(
    '"measurement_date_time" values are valid ISO 8601 timestamps with timezone offsets (e.g. "2025-02-15T10:30:00-08:00")'
)
def step_impl(context: Context):
    pass


@given("the CSV includes optional fields when available:")
def step_impl(context: Context):
    pass


@when("I run the CLI command:")
def step_impl(context: Context):
    pass


@then("the command exits with code 0")
def step_impl(context: Context):
    """ """
    raise NotImplementedError("STEP: Then the command exits with code 0")


@then("stdout should be valid JSON")
def step_impl(context: Context):
    raise NotImplementedError("STEP: And stdout should be valid JSON")


@then("stdout includes a summary containing:")
def step_impl(context: Context):
    pass


@then("stdout includes an array of created water level entry objects")
def step_impl(context: Context):
    raise NotImplementedError(
        "STEP: And stdout includes an array of created water level entry objects"
    )


@then("stderr should be empty")
def step_impl(context: Context):
    raise NotImplementedError("STEP: And stderr should be empty")


# ================================================================================
# Upload succeeds when required columns are present but in a different order
# ================================================================================
@given("my CSV file contains all required headers but in a different column order")
def step_impl(context: Context):

    raise NotImplementedError(
        "STEP: Given my CSV file contains all required headers but in a different column order"
    )


@then("all water level entries are imported")
def step_impl(context: Context):
    raise NotImplementedError("STEP: And all water level entries are imported")


# ================================================================================
# Upload succeeds when CSV contains extra, unknown columns
# ================================================================================
@given("my CSV file contains extra columns but is otherwise valid")
def step_impl(context: Context):
    raise NotImplementedError(
        "STEP: Given my CSV file contains extra columns but is otherwise valid"
    )


# ================================================================================
# No water level entries are imported when any row fails validation
# ================================================================================


@given(
    'my CSV file contains 3 rows of data with 2 valid rows and 1 row missing the required "well_name_point_id"'
)
def step_impl(context: Context):
    raise NotImplementedError(
        'STEP: Given my CSV file contains 3 rows of data with 2 valid rows and 1 row missing the required "well_name_point_id"'
    )


@then("the command exits with a non-zero exit code")
def step_impl(context: Context):
    raise NotImplementedError("STEP: Then the command exits with a non-zero exit code")


@then(
    'stderr should contain a validation error for the row missing "well_name_point_id"'
)
def step_impl(context: Context):
    raise NotImplementedError(
        'STEP: And stderr should contain a validation error for the row missing "well_name_point_id"'
    )


@then("no water level entries are imported")
def step_impl(context: Context):
    raise NotImplementedError("STEP: And no water level entries are imported")


# ================================================================================
# Upload fails when a required field is missing
# ================================================================================
@given('my CSV file contains a row missing the required "{required_field}" field')
def step_impl(context: Context, required_field: str):
    raise NotImplementedError(
        'STEP: Given my CSV file contains a row missing the required "<required_field>" field'
    )


@then('stderr should contain a validation error for the "{required_field}" field')
def step_impl(context: Context, required_field: str):
    raise NotImplementedError(
        'STEP: And stderr should contain a validation error for the "<required_field>" field'
    )


# ================================================================================
# Upload fails due to invalid date formats
# ================================================================================
@given(
    'my CSV file contains invalid ISO 8601 date values in the "measurement_date_time" field'
)
def step_impl(context: Context):
    raise NotImplementedError(
        'STEP: Given my CSV file contains invalid ISO 8601 date values in the "measurement_date_time" field'
    )


@then("stderr should contain validation errors identifying the invalid field and row")
def step_impl(context: Context):
    raise NotImplementedError(
        "STEP: And stderr should contain validation errors identifying the invalid field and row"
    )


# ================================================================================
# Upload fails due to invalid numeric fields
# ================================================================================
@given(
    'my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "mp_height" or "depth_to_water_ft"'
)
def step_impl(context: Context):
    raise NotImplementedError(
        'STEP: Given my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "mp_height" or "depth_to_water_ft"'
    )


# ================================================================================
# Upload fails due to invalid lexicon values
# ================================================================================
@given(
    'my CSV file contains invalid lexicon values for "sampler", "sample_method", "level_status", or "data_quality"'
)
def step_impl(context: Context):
    raise NotImplementedError(
        'STEP: Given my CSV file contains invalid lexicon values for "sampler", "sample_method", "level_status", or "data_quality"'
    )


# ============= EOF =============================================
