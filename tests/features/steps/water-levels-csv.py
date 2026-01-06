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
from datetime import datetime, timedelta
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

from behave import given, when, then
from behave.runner import Context

from db import Observation, FieldEvent, Sample
from db.engine import session_ctx
from schemas.water_level_csv import WaterLevelCsvRow
from services.water_level_csv import bulk_upload_water_levels


def _available_well_names(context: Context) -> list[str]:
    if not hasattr(context, "well_names"):
        context.well_names = [well.name for well in context.objects["wells"]]
    return context.well_names


def _available_field_staff(context: Context) -> list[str]:
    if not hasattr(context, "contact_names"):
        context.contact_names = [
            contact.name for contact in context.objects["contacts"]
        ]
    return context.contact_names


def _base_row(context: Context, index: int) -> Dict[str, str]:
    well_names = _available_well_names(context)
    well_name = well_names[(index - 1) % len(well_names)]

    contact_names = _available_field_staff(context)
    measurement_day = 14 + index
    row = WaterLevelCsvRow(
        well_name_point_id=well_name,
        field_event_date_time=f"2025-02-{measurement_day:02d}T08:00:00",
        field_staff=contact_names[(index - 1) % len(contact_names)],
        field_staff_2=contact_names[(index - 2) % len(contact_names)],
        field_staff_3=contact_names[(index - 3) % len(contact_names)],
        water_level_date_time=f"2025-02-{measurement_day:02d}T10:30:00",
        measuring_person=contact_names[(index - 1) % len(contact_names)],
        sample_method="Steel-tape measurement",
        mp_height=1.5 if index == 1 else 1.8,
        level_status="Water level not affected",
        depth_to_water_ft=9 if index == 1 else 8,
        data_quality="Water level accurate to within two hundreths of a foot",
    )
    return row.model_dump(mode="json")


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
    context.file_content = csv_text  # file_context needs to be set for shared given


def _set_rows(
    context: Context, rows: List[Dict[str, str]], headers: List[str] | None = None
) -> None:
    context.csv_rows = rows
    if headers is not None:
        context.csv_headers = headers
    elif rows:
        context.csv_headers = list(rows[0].keys())
    else:
        context.csv_headers = [field for field in WaterLevelCsvRow.model_fields.keys()]
    _write_csv_to_context(context)
    context.stdout_json = None

    # set context.rows to be all rows and the header for optional step
    context.rows = rows


def _ensure_stdout_json(context: Context) -> Dict[str, Any]:
    if not hasattr(context, "stdout_json") or context.stdout_json is None:
        context.stdout_json = json.loads(context.cli_result.stdout)
    return context.stdout_json


# ============================================================================
# Scenario: Uploading a valid water level entry CSV containing required fields
# ============================================================================
@given("a valid CSV file for bulk water level entry upload")
def step_impl(context: Context):
    rows = _build_valid_rows(context)
    _set_rows(context, rows)


@given("my CSV file contains multiple rows of water level entry data")
def step_impl(context: Context):
    assert len(context.csv_rows) >= 2


@given("the water level CSV includes required fields:")
def step_impl(context: Context):
    field_name = context.table.headings[0]
    expected_fields = [row[field_name].strip() for row in context.table]
    headers = set(context.csv_headers)
    missing = [field for field in expected_fields if field not in headers]
    assert not missing, f"Missing required headers: {missing}"

    context.required_fields = expected_fields


@given('each "well_name_point_id" value matches an existing well')
def step_impl(context: Context):
    available = set(_available_well_names(context))
    for row in context.csv_rows:
        assert (
            row["well_name_point_id"] in available
        ), f"Unknown well identifier {row['well_name_point_id']}"


@given(
    '"water_level_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T10:30:00")'
)
def step_impl(context: Context):
    for row in context.csv_rows:
        assert row["water_level_date_time"].startswith("2025-02")
        assert "T" in row["water_level_date_time"]
        dt_naive = datetime.strptime(row["water_level_date_time"], "%Y-%m-%dT%H:%M:%S")
        assert (
            dt_naive.tzinfo is None
        ), f"Expected timezone-naive datetime but got {row['water_level_date_time']}"


@given("the water level CSV includes optional fields when available:")
def step_impl(context: Context):
    field_name = context.table.headings[0]
    optional_fields = [row[field_name].strip() for row in context.table]
    headers = set(context.csv_headers)
    missing = [field for field in optional_fields if field not in headers]
    assert not missing, f"Missing optional headers: {missing}"


@when("I run the CLI command:")
def step_impl(context: Context):
    command_text = (context.text or "").strip()
    context.command_text = command_text
    output_json = "--output json" in command_text.lower()
    _write_csv_to_context(context)
    context.cli_result = bulk_upload_water_levels(
        context.csv_file, pretty_json=output_json
    )
    context.stdout_json = None


@then(
    "all datetime objects are assigned the correct Mountain Time timezone offset based on the date value. "
)
def step_impl(context: Context):
    with session_ctx() as session:
        for field in ["field_event_date_time", "water_level_date_time"]:
            for i, row in enumerate(context.csv_rows):
                dt_str = row[field]
                dt_naive = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                tz = ZoneInfo("America/Denver")
                dt_aware = dt_naive.replace(tzinfo=tz)

                if field == "field_event_date_time":
                    field_event = session.query(FieldEvent).one_or_none(
                        FieldEvent.id
                        == context.cli_result.payload.water_levels[i].field_event_id
                    )
                    assert (
                        field_event.event_date == dt_aware
                    ), f"Expected {dt_aware} but got {field_event.event_date} for row {i+1}"
                    assert field_event.utcoffset() == timedelta(hours=-7)
                else:
                    observation = session.query(Observation).one_or_none(
                        Observation.id
                        == context.cli_result.payload.water_levels[i].observation_id
                    )
                    assert (
                        observation.observation_datetime == dt_aware
                    ), f"Expected {dt_aware} but got {observation.observation_datetime} for row {i+1}"
                    assert observation.observation_datetime.utcoffset() == timedelta(
                        hours=-7
                    )

                    sample = session.query(Sample).one_or_none(
                        Sample.id
                        == context.cli_result.payload.water_levels[i].sample_id
                    )
                    assert (
                        sample.sample_date == dt_aware
                    ), f"Expected {dt_aware} but got {sample.sample_date} for row {i+1}"
                    assert sample.sample_date.utcoffset() == timedelta(hours=-7)


@then("the command exits with code 0")
def step_impl(context: Context):
    assert context.cli_result.exit_code == 0, context.cli_result.stderr


@then("stdout should be valid JSON")
def step_impl(context: Context):
    _ensure_stdout_json(context)


@then("stdout includes a summary containing:")
def step_impl(context: Context):
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
def step_impl(context: Context):
    payload = _ensure_stdout_json(context)
    rows = payload.get("water_levels", [])
    assert rows, "Expected created water level records"
    with session_ctx() as session:
        for row in rows:
            assert "well_name_point_id" in row
            assert "water_level_date_time" in row
            obs = session.get(Observation, row["observation_id"])
            assert obs is not None, "Observation missing from database"


@then("stderr should be empty")
def step_impl(context: Context):
    assert context.cli_result.stderr == ""


# ============================================================================
# Scenario: Upload succeeds when required columns are present but reordered
# ============================================================================
@given(
    "my water level CSV file contains all required headers but in a different column order"
)
def step_impl(context: Context):
    rows = _build_valid_rows(context)
    headers = list(reversed(list(rows[0].keys())))
    _set_rows(context, rows, headers=headers)
    assert headers != list(rows[0].keys())


@then("all water level entries are imported")
def step_impl(context: Context):
    payload = _ensure_stdout_json(context)
    summary = payload["summary"]
    assert summary["total_rows_processed"] == summary["total_rows_imported"]
    assert summary["total_rows_imported"] > 0


# ============================================================================
# Scenario: Upload succeeds when CSV contains extra columns
# ============================================================================
@given("my water level CSV file contains extra columns but is otherwise valid")
def step_impl(context: Context):
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
def step_impl(context: Context):
    rows = _build_valid_rows(context, count=3)
    rows[2]["well_name_point_id"] = ""
    _set_rows(context, rows)
    context.missing_field = "well_name_point_id"


@then("the command exits with a non-zero exit code")
def step_impl(context: Context):
    assert context.cli_result.exit_code != 0


@then(
    'stderr should contain a validation error for the row missing "well_name_point_id"'
)
def step_impl(context: Context):
    assert "well_name_point_id" in context.cli_result.stderr


@then("no water level entries are imported")
def step_impl(context: Context):
    payload = _ensure_stdout_json(context)
    summary = payload["summary"]
    assert summary["total_rows_imported"] == 0


# ============================================================================
# Scenario Outline: Upload fails when a required field is missing
# ============================================================================
@given(
    'my water level CSV file contains a row missing the required "{required_field}" field'
)
def step_impl(context: Context, required_field: str):
    rows = _build_valid_rows(context, count=1)
    rows[0][required_field] = ""
    _set_rows(context, rows)
    context.missing_field = required_field


@then('stderr should contain a validation error for the "{required_field}" field')
def step_impl(context: Context, required_field: str):
    assert required_field in context.cli_result.stderr


# ============================================================================
# Scenario: Upload fails due to invalid date formats
# ============================================================================
@given(
    'my CSV file contains invalid ISO 8601 date values in the "water_level_date_time" field'
)
def step_impl(context: Context):
    rows = _build_valid_rows(context, count=1)
    rows[0]["water_level_date_time"] = "02/15/2025 10:30"
    _set_rows(context, rows)
    context.invalid_fields = ["water_level_date_time"]


@then("stderr should contain validation errors identifying the invalid field and row")
def step_impl(context: Context):
    stderr = context.cli_result.stderr
    assert stderr, "Expected stderr output"
    for field in getattr(context, "invalid_fields", []):
        assert field in stderr
    assert "Row" in stderr


# ============================================================================
# Scenario: Upload fails due to invalid numeric fields
# ============================================================================
@given(
    'my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "mp_height" or "depth_to_water_ft"'
)
def step_impl(context: Context):
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
def step_impl(context: Context):
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


# ============= EOF =============================================
