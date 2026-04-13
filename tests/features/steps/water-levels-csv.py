# ==============================================================================
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
# ==============================================================================
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from behave import given, when, then
from behave.runner import Context
from db import Observation
from db.engine import session_ctx
from services.water_level_csv import bulk_upload_water_levels
from tests.features.environment import (
    add_location,
    add_measuring_point_history,
    add_well,
)

REQUIRED_FIELDS: List[str] = [
    "field_staff",
    "well_name_point_id",
    "field_event_date_time",
    "water_level_date_time",
    "measuring_person",
    "sample_method",
]
OPTIONAL_FIELDS = [
    "field_staff_2",
    "field_staff_3",
    "mp_height",
    "level_status",
    "depth_to_water_ft",
    "data_quality",
    "water_level_notes",
]
VALID_SAMPLE_METHODS = [
    "Electric tape measurement (E-probe)",
    "Steel-tape measurement",
]
VALID_LEVEL_STATUSES = ["Water level not affected", "Site was dry"]
VALID_DATA_QUALITIES = [
    "Water level accurate to within two hundreths of a foot",
    "None",
]


def _available_well_names(context: Context) -> list[str]:
    if "wells" not in context.objects or not context.objects["wells"]:
        with session_ctx() as session:
            loc_1 = add_location(context, session)
            loc_2 = add_location(context, session)
            well_1 = add_well(context, session, loc_1, name_num=101)
            well_2 = add_well(context, session, loc_2, name_num=102)
            add_measuring_point_history(context, session, well_1)
            add_measuring_point_history(context, session, well_2)

    if not hasattr(context, "well_names"):
        context.well_names = [well.name for well in context.objects["wells"]]
    return context.well_names


def _base_row(context: Context, index: int) -> Dict[str, str]:
    well_names = _available_well_names(context)
    well_name = well_names[(index - 1) % len(well_names)]
    measurement_day = 14 + index
    field_staff = "A Lopez" if index == 1 else "B Chen"
    return {
        "field_staff": field_staff,
        "field_staff_2": "",
        "field_staff_3": "",
        "well_name_point_id": well_name,
        "field_event_date_time": f"2025-02-{measurement_day:02d}T08:00:00",
        "water_level_date_time": f"2025-02-{measurement_day:02d}T10:30:00",
        "measuring_person": field_staff,
        "sample_method": VALID_SAMPLE_METHODS[(index - 1) % len(VALID_SAMPLE_METHODS)],
        "mp_height": "1.5" if index == 1 else "1.8",
        "level_status": VALID_LEVEL_STATUSES[(index - 1) % len(VALID_LEVEL_STATUSES)],
        "depth_to_water_ft": "7.0" if index == 1 else "",
        "data_quality": VALID_DATA_QUALITIES[(index - 1) % len(VALID_DATA_QUALITIES)],
        "water_level_notes": "Initial measurement" if index == 1 else "Follow-up",
    }


def _build_valid_rows(context: Context, count: int = 2) -> List[Dict[str, str]]:
    return [_base_row(context, i + 1) for i in range(count)]


def _serialize_csv(rows: List[Dict[str, Any]], headers: Iterable[str]) -> str:
    header_line = ",".join(headers)
    data_lines = []
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        data_lines.append(",".join(values))
    return "\n".join([header_line, *data_lines])


def _write_csv_to_context(context: Context) -> None:
    csv_text = _serialize_csv(context.csv_rows, context.csv_headers)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    temp_file.write(csv_text.encode("utf-8"))
    temp_file.flush()
    temp_file.close()
    context.csv_file = str(Path(temp_file.name))
    context.csv_raw_text = csv_text
    context.file_content = csv_text


def _set_rows(
    context: Context, rows: List[Dict[str, str]], headers: List[str] | None = None
) -> None:
    context.csv_rows = rows
    if headers is not None:
        context.csv_headers = headers
    elif rows:
        context.csv_headers = list(rows[0].keys())
    else:
        context.csv_headers = list(REQUIRED_FIELDS)
    _write_csv_to_context(context)
    context.stdout_json = None


def _ensure_stdout_json(context: Context) -> Dict[str, Any]:
    if not hasattr(context, "stdout_json") or context.stdout_json is None:
        context.stdout_json = json.loads(context.cli_result.stdout)
    return context.stdout_json


# ============================================================================
# Scenario: Uploading a valid water level entry CSV containing required fields
# ============================================================================
@given("a valid CSV file for bulk water level entry upload")
def step_given_a_valid_csv_file_for_bulk_water_level_entry_upload(context: Context):
    rows = _build_valid_rows(context)
    _set_rows(context, rows)


@given("my CSV file contains multiple rows of water level entry data")
def step_given_my_csv_file_contains_multiple_rows_of_water_level_entry(
    context: Context,
):
    assert len(context.csv_rows) >= 2


@given("the water level CSV includes required fields:")
def step_given_the_water_level_csv_includes_required_fields(context: Context):
    field_name = context.table.headings[0]
    expected_fields = [row[field_name].strip() for row in context.table]
    headers = set(context.csv_headers)
    missing = [field for field in expected_fields if field not in headers]
    assert not missing, f"Missing required headers: {missing}"


@given('each "well_name_point_id" value matches an existing well')
def step_given_each_well_name_point_id_value_matches_an_existing_well(context: Context):
    available = set(_available_well_names(context))
    for row in context.csv_rows:
        assert (
            row["well_name_point_id"] in available
        ), f"Unknown well identifier {row['well_name_point_id']}"


@given(
    '"field_event_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T08:00:00")'
)
def step_given_field_event_date_time_values_are_valid_naive_iso_datetimes(
    context: Context,
):
    for row in context.csv_rows:
        assert row["field_event_date_time"].startswith("2025-02")
        assert "T" in row["field_event_date_time"]
        assert "+" not in row["field_event_date_time"]
        assert row["field_event_date_time"].count(":") == 2


@given(
    '"water_level_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T10:30:00")'
)
def step_given_water_level_date_time_values_are_valid_naive_iso_datetimes(
    context: Context,
):
    for row in context.csv_rows:
        assert row["water_level_date_time"].startswith("2025-02")
        assert "T" in row["water_level_date_time"]
        assert "+" not in row["water_level_date_time"]
        assert row["water_level_date_time"].count(":") == 2


@given(
    'when provided, "sample_method", "level_status", and "data_quality" values are valid lexicon values'
)
def step_given_lexicon_values_are_valid(context: Context):
    for row in context.csv_rows:
        if row.get("sample_method"):
            assert row["sample_method"] in VALID_SAMPLE_METHODS
        if row.get("level_status"):
            assert row["level_status"] in VALID_LEVEL_STATUSES
        if row.get("data_quality"):
            assert row["data_quality"] in VALID_DATA_QUALITIES


@given("the water level CSV includes optional fields when available:")
def step_given_the_water_level_csv_includes_optional_fields_when_available(
    context: Context,
):
    field_name = context.table.headings[0]
    optional_fields = [row[field_name].strip() for row in context.table]
    headers = set(context.csv_headers)
    missing = [field for field in optional_fields if field not in headers]
    assert not missing, f"Missing optional headers: {missing}"


@when("I run the CLI command:")
def step_when_i_run_the_cli_command(context: Context):
    command_text = (context.text or "").strip()
    context.command_text = command_text
    output_json = "--output json" in command_text.lower()
    _write_csv_to_context(context)
    context.cli_result = bulk_upload_water_levels(
        context.csv_file, pretty_json=output_json
    )
    context.stdout_json = None


@then("stdout should be valid JSON")
def step_then_stdout_should_be_valid_json(context: Context):
    _ensure_stdout_json(context)


@then("stdout includes a summary containing:")
def step_then_stdout_includes_a_summary_containing(context: Context):
    payload = _ensure_stdout_json(context)
    summary = payload.get("summary", {})
    for row in context.table:
        field = row[context.table.headings[0]].strip()
        expected_value = row[context.table.headings[1]].strip()
        actual = summary.get(field)
        expected = int(expected_value) if expected_value.isdigit() else expected_value
        assert (
            actual == expected
        ), f"Summary field {field} expected {expected} but got {actual}"


@then("stdout includes an array of created water level entry objects")
def step_then_stdout_includes_an_array_of_created_water_level_entry_objects(
    context: Context,
):
    payload = _ensure_stdout_json(context)
    rows = payload.get("water_levels", [])
    assert rows, "Expected created water level records"
    with session_ctx() as session:
        for row in rows:
            assert "well_name_point_id" in row
            assert "measurement_date_time" in row
            obs = session.get(Observation, row["observation_id"])
            assert obs is not None, "Observation missing from database"


@then("stderr should be empty")
def step_then_stderr_should_be_empty(context: Context):
    assert context.cli_result.stderr == ""


# ============================================================================
# Scenario: Upload succeeds when required columns are present but reordered
# ============================================================================
@given(
    "my water level CSV file uses legacy alias headers for measurement date, sampler, and measuring point height"
)
def step_given_my_water_level_csv_file_uses_legacy_alias_headers(context: Context):
    rows = _build_valid_rows(context)
    alias_rows = []
    for row in rows:
        alias_row = dict(row)
        alias_row["measurement_date_time"] = alias_row.pop("water_level_date_time")
        alias_row["sampler"] = alias_row.pop("measuring_person")
        alias_row["mp_height_ft"] = alias_row.pop("mp_height")
        alias_rows.append(alias_row)
    headers = list(alias_rows[0].keys())
    _set_rows(context, alias_rows, headers=headers)


@given(
    "my water level CSV file contains all required headers but in a different column order"
)
def step_given_my_water_level_csv_file_contains_reordered_headers(context: Context):
    rows = _build_valid_rows(context)
    headers = list(reversed(list(rows[0].keys())))
    _set_rows(context, rows, headers=headers)
    assert headers != list(rows[0].keys())


@then("all water level entries are imported")
def step_then_all_water_level_entries_are_imported(context: Context):
    payload = _ensure_stdout_json(context)
    summary = payload["summary"]
    assert summary["total_rows_processed"] == summary["total_rows_imported"]
    assert summary["total_rows_imported"] > 0


# ============================================================================
# Scenario: Upload succeeds when CSV contains extra columns
# ============================================================================
@given("my water level CSV file contains extra columns but is otherwise valid")
def step_given_my_water_level_csv_file_contains_extra_columns_but_is(context: Context):
    rows = _build_valid_rows(context)
    for idx, row in enumerate(rows):
        row["custom_note"] = f"extra-{idx}"
    headers = list(rows[0].keys())
    _set_rows(context, rows, headers=headers)
    assert "custom_note" in context.csv_headers


# ============================================================================
# Scenario: No entries imported when any row fails validation
# ============================================================================
@given(
    'my water level CSV contains 3 rows with 2 valid rows and 1 row missing the required "well_name_point_id"'
)
def step_step_step_3(context: Context):
    rows = _build_valid_rows(context, count=3)
    rows[2]["well_name_point_id"] = ""
    _set_rows(context, rows)
    context.missing_field = "well_name_point_id"


@then(
    'stderr should contain a validation error for the row missing "well_name_point_id"'
)
def step_step_step_4(context: Context):
    assert "well_name_point_id" in context.cli_result.stderr


@then("no water level entries are imported")
def step_then_no_water_level_entries_are_imported(context: Context):
    payload = _ensure_stdout_json(context)
    summary = payload["summary"]
    assert summary["total_rows_imported"] == 0


# ============================================================================
# Scenario Outline: Upload fails when a required field is missing
# ============================================================================
@given(
    'my water level CSV file contains a row missing the required "{required_field}" field'
)
def step_step_step_5(context: Context, required_field: str):
    rows = _build_valid_rows(context, count=1)
    rows[0][required_field] = ""
    _set_rows(context, rows)
    context.missing_field = required_field


@then('stderr should contain a validation error for the "{required_field}" field')
def step_then_stderr_should_contain_a_validation_error_for_the_required_field(
    context: Context, required_field: str
):
    assert required_field in context.cli_result.stderr


# ============================================================================
# Scenario: Upload fails due to invalid date formats
# ============================================================================
@given(
    'my CSV file contains invalid ISO 8601 date values in the "water_level_date_time" field'
)
def step_step_step_6(context: Context):
    rows = _build_valid_rows(context, count=1)
    rows[0]["water_level_date_time"] = "02/15/2025 10:30"
    _set_rows(context, rows)
    context.invalid_fields = ["water_level_date_time"]


@then("stderr should contain validation errors identifying the invalid field and row")
def step_then_stderr_should_contain_validation_errors_identifying_the_invalid_field_and(
    context: Context,
):
    stderr = context.cli_result.stderr
    assert stderr, "Expected stderr output"
    for field in getattr(context, "invalid_fields", []):
        assert field in stderr
    assert "Row" in stderr


# ============================================================================
# Scenario: Upload fails due to invalid numeric fields
# ============================================================================
@given(
    'my CSV file contains values that cannot be parsed as numeric in numeric fields such as "mp_height" or "depth_to_water_ft"'
)
def step_step_step_7(context: Context):
    rows = _build_valid_rows(context, count=1)
    rows[0]["mp_height"] = "one point five"
    rows[0]["depth_to_water_ft"] = "forty"
    _set_rows(context, rows)
    context.invalid_fields = ["mp_height", "depth_to_water_ft"]


# ============================================================================
# Scenario: Upload fails due to invalid lexicon values
# ============================================================================
@given(
    'my CSV file contains invalid lexicon values for "sample_method", "level_status", or "data_quality"'
)
def step_step_step_8(context: Context):
    rows = _build_valid_rows(context, count=1)
    rows[0]["sample_method"] = "mystery"
    rows[0]["level_status"] = "supercharged"
    rows[0]["data_quality"] = "bad"
    _set_rows(context, rows)
    context.invalid_fields = [
        "sample_method",
        "level_status",
        "data_quality",
    ]


@given(
    "my water level CSV file contains a row where measuring_person is not one of the supplied field staff"
)
def step_given_measuring_person_is_not_one_of_the_supplied_field_staff(
    context: Context,
):
    rows = _build_valid_rows(context, count=1)
    rows[0]["measuring_person"] = "Unexpected Person"
    _set_rows(context, rows)
    context.invalid_fields = ["measuring_person"]


# ============= EOF =============================================
