import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from behave import given, when, then
from behave.runner import Context
from cli.service_adapter import well_inventory_csv
from db.engine import session_ctx
from db.lexicon import LexiconCategory
from services.util import convert_dt_tz_naive_to_tz_aware
from sqlalchemy import select


@given("valid lexicon values exist for:")
def step_impl_valid_lexicon_values(context: Context):
    with session_ctx() as session:
        for row in context.table:
            category = row[0]
            found = session.scalars(
                select(LexiconCategory).where(LexiconCategory.name == category)
            ).one_or_none()
            assert found is not None, f"Invalid lexicon category: {category}"


@given("the CSV includes required fields:")
def step_impl_csv_includes_required_fields(context: Context):
    """Sets up the CSV file with multiple rows of well inventory data."""
    context.required_fields = [row[0] for row in context.table]
    keys = context.rows[0].keys()
    for field in context.required_fields:
        assert field in keys, f"Missing required field: {field}"


@given('each "well_name_point_id" value is unique per row')
def step_given_each_well_name_point_id_value_is_unique_per_row(context: Context):
    """Verifies that each "well_name_point_id" value is unique per row."""
    seen_ids = set()
    for row in context.rows:
        if row["well_name_point_id"] in seen_ids:
            raise ValueError(
                f"Duplicate well_name_point_id: {row['well_name_point_id']}"
            )
        seen_ids.add(row["well_name_point_id"])


@given("the CSV includes optional fields when available:")
def step_given_the_csv_includes_optional_fields_when_available(context: Context):
    optional_fields = [row[0] for row in context.table]
    keys = context.rows[0].keys()

    for key in keys:
        if key not in context.required_fields:
            assert key in optional_fields, f"Unexpected field found: {key}"


@given("the csv includes optional water level entry fields when available:")
def step_given_the_csv_includes_optional_water_level_entry_fields_when_available(
    context: Context,
):
    optional_fields = [row[0] for row in context.table]
    context.water_level_optional_fields = optional_fields


@given(
    'the required "date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T10:30:00")'
)
def step_step_step(context: Context):
    """Verifies that "date_time" values are valid ISO 8601 timezone-naive datetime strings."""
    for row in context.rows:
        try:
            date_time = datetime.fromisoformat(row["date_time"])
            assert (
                date_time.tzinfo is None
            ), f"date_time should be timezone-naive: {row['date_time']}"
        except ValueError as e:
            raise ValueError(f"Invalid date_time: {row['date_time']}") from e


@given(
    'the optional "water_level_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T10:30:00") when provided'
)
def step_step_step_2(context: Context):
    """Verifies that "water_level_date_time" values are valid ISO 8601 timezone-naive datetime strings."""
    for row in context.rows:
        if row.get("water_level_date_time", None):
            try:
                date_time = datetime.fromisoformat(row["water_level_date_time"])
                assert (
                    date_time.tzinfo is None
                ), f"water_level_date_time should be timezone-naive: {row['water_level_date_time']}"
            except ValueError as e:
                raise ValueError(
                    f"Invalid water_level_date_time: {row['water_level_date_time']}"
                ) from e


@when("I upload the file to the bulk upload endpoint")
@when("I run the well inventory bulk upload command")
def step_when_i_run_the_well_inventory_bulk_upload_command(context: Context):
    suffix = Path(getattr(context, "file_name", "upload.csv")).suffix or ".csv"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as fp:
        fp.write(context.file_content)
        temp_path = Path(fp.name)

    try:
        context.upload_file_path = temp_path
        context.cli_result = well_inventory_csv(temp_path)
        context.response = _WellInventoryCliResponse(context.cli_result)
    finally:
        temp_path.unlink(missing_ok=True)


class _WellInventoryCliResponse:
    def __init__(self, cli_result):
        self._cli_result = cli_result
        self.headers = {"Content-Type": "application/json"}
        self._json = self._normalize_payload(cli_result.payload)
        self.status_code = self._infer_status_code(
            cli_result.payload, cli_result.exit_code
        )
        self.text = json.dumps(self._json)

    @staticmethod
    def _infer_status_code(payload: dict, exit_code: int) -> int:
        if exit_code == 0:
            return 201
        if payload.get("validation_errors"):
            return 422
        return 400

    @staticmethod
    def _normalize_payload(payload: dict) -> dict:
        # Keep feature assertions API-compatible while execution happens via CLI.
        if "detail" in payload and isinstance(payload["detail"], str):
            return {"detail": [{"msg": payload["detail"]}]}
        return payload

    def json(self):
        return self._json


@then(
    "all datetime objects are assigned the correct Mountain Time timezone offset based on the date value."
)
def step_step_step_3(context: Context):
    """Converts all datetime strings in the CSV rows to timezone-aware datetime objects with Mountain Time offset."""
    for i, row in enumerate(context.rows):
        # Convert date_time field
        date_time_naive = datetime.fromisoformat(row["date_time"])
        date_time_aware = convert_dt_tz_naive_to_tz_aware(
            date_time_naive, "America/Denver"
        )
        row["date_time"] = date_time_aware.isoformat()

        # confirm correct time zone and offset
        if i == 0:
            # MST, offset -07:00
            assert date_time_aware.utcoffset() == timedelta(
                hours=-7
            ), "date_time offset is not -07:00"
        else:
            # MDT, offset -06:00
            assert date_time_aware.utcoffset() == timedelta(
                hours=-6
            ), "date_time offset is not -06:00"

        # confirm the time was not changed from what was provided
        assert (
            date_time_aware.replace(tzinfo=None) == date_time_naive
        ), "date_time value was changed during timezone assignment"

        # Convert water_level_date_time field if it exists
        if row.get("water_level_date_time", None):
            wl_date_time_naive = datetime.fromisoformat(row["water_level_date_time"])
            wl_date_time_aware = convert_dt_tz_naive_to_tz_aware(
                wl_date_time_naive, "America/Denver"
            )
            row["water_level_date_time"] = wl_date_time_aware.isoformat()

            if wl_date_time_aware.dst():
                # MDT, offset -06:00
                assert wl_date_time_aware.utcoffset() == timedelta(
                    hours=-6
                ), "water_level_date_time offset is not -06:00"
            else:
                # MST, offset -07:00
                assert wl_date_time_aware.utcoffset() == timedelta(
                    hours=-7
                ), "water_level_date_time offset is not -07:00"

            assert (
                wl_date_time_aware.replace(tzinfo=None) == wl_date_time_naive
            ), "water_level_date_time value was changed during timezone assignment"


@then("the response includes a summary containing:")
def step_then_the_response_includes_a_summary_containing(context: Context):
    response_json = context.response.json()
    summary = response_json.get("summary", {})
    for row in context.table:
        field = row[0]
        expected_value = int(row[1])
        actual_value = summary.get(field)
        assert (
            actual_value == expected_value
        ), f"Expected {expected_value} for {field}, but got {actual_value}"


@then("the response includes an array of created well objects")
def step_then_the_response_includes_an_array_of_created_well_objects(context: Context):
    response_json = context.response.json()
    wells = response_json.get("wells", [])
    assert (
        len(wells) == context.row_count
    ), "Expected the same number of wells as rows in the CSV"


@then("the response includes validation errors for all rows missing required fields")
def step_then_the_response_includes_validation_errors_for_all_rows_missing_required(
    context: Context,
):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == len(
        context.rows
    ), "Expected the same number of validation errors as rows in the CSV"
    error_fields = [
        e["row"] for e in validation_errors if e["field"] == "well_name_point_id"
    ]
    for i, row in enumerate(context.rows):
        if row["well_name_point_id"] == "":
            assert i + 1 in error_fields, f"Missing required field for row {row}"


@then("the response identifies the row and field for each error")
def step_then_the_response_identifies_the_row_and_field_for_each_error(
    context: Context,
):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "row" in error, "Expected validation error to include row number"
        assert "field" in error, "Expected validation error to include field name"


@then("no wells are imported")
def step_then_no_wells_are_imported(context: Context):
    response_json = context.response.json()
    wells = response_json.get("wells", [])
    assert len(wells) == 0, "Expected no wells to be imported"


@then("the response includes validation errors indicating duplicated values")
def step_then_the_response_includes_validation_errors_indicating_duplicated_values(
    context: Context,
):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])

    assert len(validation_errors) == 1, "Expected 1 validation error"

    error_fields = [
        e["row"] for e in validation_errors if e["field"] == "well_name_point_id"
    ]
    assert error_fields == [2], f"Expected duplicated values for row {error_fields}"
    assert (
        validation_errors[0]["error"] == "Duplicate value for well_name_point_id"
    ), "Expected duplicated values for row 2"


@then("each error identifies the row and field")
def step_then_each_error_identifies_the_row_and_field(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "row" in error, "Expected validation error to include row number"
        assert "field" in error, "Expected validation error to include field name"


@then("the response includes validation errors identifying the invalid field and row")
def step_then_the_response_includes_validation_errors_identifying_the_invalid_field_and(
    context: Context,
):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "field" in error, "Expected validation error to include field name"
        assert "error" in error, "Expected validation error to include error message"


@then("the response includes an error message indicating unsupported file type")
def step_then_the_response_includes_an_error_message_indicating_unsupported_file_type(
    context: Context,
):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "Unsupported file type"
    ), "Expected error message to indicate unsupported file type"


@then("the response includes an error message indicating an empty file")
def step_then_the_response_includes_an_error_message_indicating_an_empty_file(
    context: Context,
):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "Empty file"
    ), "Expected error message to indicate an empty file"


@then("the response includes an error indicating that no data rows were found")
def step_then_the_response_includes_an_error_indicating_that_no_data_rows(
    context: Context,
):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "No data rows found"
    ), "Expected error message to indicate no data rows were found"


@then("all wells are imported")
def step_then_all_wells_are_imported(context: Context):
    response_json = context.response.json()
    assert "wells" in response_json, "Expected response to include wells"
    assert len(response_json["wells"]) == context.row_count


@then(
    'the response includes a validation error for the row missing "well_name_point_id"'
)
def step_step_step_4(context: Context):
    response_json = context.response.json()
    assert "summary" in response_json, "Expected summary in response"
    summary = response_json["summary"]
    assert "total_rows_processed" in summary, "Expected total_rows_processed"
    assert (
        summary["total_rows_processed"] == context.row_count
    ), f"Expected total_rows_processed = {context.row_count}"
    assert "total_rows_imported" in summary, "Expected total_rows_imported"
    assert summary["total_rows_imported"] == 0, "Expected total_rows_imported=0"
    assert (
        "validation_errors_or_warnings" in summary
    ), "Expected validation_errors_or_warnings"
    assert (
        summary["validation_errors_or_warnings"] == 1
    ), "Expected validation_errors_or_warnings = 1"

    assert "validation_errors" in response_json, "Expected validation_errors"
    ve = response_json["validation_errors"]
    assert (
        ve[0]["field"] == "well_name_point_id"
    ), "Expected missing field well_name_point_id"
    assert ve[0]["error"] == "Field required", "Expected Field required"


@then('the response includes a validation error for the "{required_field}" field')
def step_then_the_response_includes_a_validation_error_for_the_required_field(
    context: Context, required_field: str
):
    response_json = context.response.json()
    assert "validation_errors" in response_json, "Expected validation errors"
    vs = response_json["validation_errors"]
    assert len(vs) == 2, "Expected 2 validation error"
    assert vs[0]["field"] == required_field


@then("the response includes an error message indicating the row limit was exceeded")
def step_then_the_response_includes_an_error_message_indicating_the_row_limit(
    context: Context,
):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "Too many rows 2002>2000"
    ), "Expected error message to indicate too many rows uploaded"


@then("the response includes an error message indicating an unsupported delimiter")
def step_then_the_response_includes_an_error_message_indicating_an_unsupported_delimiter(
    context: Context,
):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"]
        == f"Unsupported delimiter '{context.delimiter}'"
    ), "Expected error message to indicate unsupported delimiter"


@then("all wells are imported with system-generated unique well_name_point_id values")
def step_then_all_wells_are_imported_with_system_generated_unique_well_name(
    context: Context,
):
    response_json = context.response.json()
    assert "wells" in response_json, "Expected response to include wells"
    wells = response_json["wells"]
    well_ids = [
        w.get("well_name_point_id") if isinstance(w, dict) else w for w in wells
    ]
    assert len(well_ids) == len(
        set(well_ids)
    ), "Expected unique well_name_point_id values"
