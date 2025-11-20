import csv
from datetime import datetime
from pathlib import Path

from behave import given, when, then
from behave.runner import Context


def _set_file_content(context: Context, name):
    path = Path("tests") / "features" / "data" / name
    with open(path, "r") as f:
        context.file_name = name
        context.file_content = f.read()
        if name.endswith(".csv"):
            context.rows = list(csv.DictReader(context.file_content.splitlines()))
            context.row_count = len(context.rows)
            context.file_type = "text/csv"
        else:
            context.rows = []
            context.row_count = 0
            context.file_type = "text/plain"


@given("a valid CSV file for bulk well inventory upload")
def step_impl_valid_csv_file(context: Context):
    _set_file_content(context, "well-inventory-valid.csv")


@given("my CSV file is encoded in UTF-8 and uses commas as separators")
def step_impl_csv_file_is_encoded_utf8(context: Context):
    """Sets the CSV file encoding to UTF-8 and sets the CSV separator to commas."""
    # context.csv_file.encoding = 'utf-8'
    # context.csv_file.separator = ','
    # determine the separator from the file content
    sample = context.file_content[:1024]
    dialect = csv.Sniffer().sniff(sample)
    assert dialect.delimiter == ","


@given("valid lexicon values exist for:")
def step_impl_valid_lexicon_values(context: Context):
    for row in context.table:
        response = context.client.get(
            "/lexicon/category",
            params={"name": row[0]},
        )
        assert response.status_code == 200, f"Invalid lexicon category: {row[0]}"


@given("my CSV file contains multiple rows of well inventory data")
def step_impl_csv_file_contains_multiple_rows(context: Context):
    """Sets up the CSV file with multiple rows of well inventory data."""
    assert len(context.rows) > 0, "CSV file contains no data rows"


@given("the CSV includes required fields:")
def step_impl_csv_includes_required_fields(context: Context):
    """Sets up the CSV file with multiple rows of well inventory data."""
    context.required_fields = [row[0] for row in context.table]
    keys = context.rows[0].keys()
    for field in context.required_fields:
        assert field in keys, f"Missing required field: {field}"


@given('each "well_name_point_id" value is unique per row')
def step_impl(context: Context):
    """Verifies that each "well_name_point_id" value is unique per row."""
    seen_ids = set()
    for row in context.rows:
        if row["well_name_point_id"] in seen_ids:
            raise ValueError(
                f"Duplicate well_name_point_id: {row['well_name_point_id']}"
            )
        seen_ids.add(row["well_name_point_id"])


@given(
    '"date_time" values are valid ISO 8601 timestamps with timezone offsets (e.g. "2025-02-15T10:30:00-08:00")'
)
def step_impl(context: Context):
    """Verifies that "date_time" values are valid ISO 8601 timestamps with timezone offsets."""
    for row in context.rows:
        try:
            datetime.fromisoformat(row["date_time"])
        except ValueError as e:
            raise ValueError(f"Invalid date_time: {row['date_time']}") from e


@given("the CSV includes optional fields when available:")
def step_impl(context: Context):
    optional_fields = [row[0] for row in context.table]
    print(f"Optional fields: {optional_fields}")


@when("I upload the file to the bulk upload endpoint")
def step_impl(context: Context):
    context.response = context.client.post(
        "/well-inventory-csv",
        files={"file": (context.file_name, context.file_content, context.file_type)},
    )


@then("the response includes a summary containing:")
def step_impl(context: Context):
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
def step_impl(context: Context):
    response_json = context.response.json()
    wells = response_json.get("wells", [])
    assert (
        len(wells) == context.row_count
    ), "Expected the same number of wells as rows in the CSV"


@given('my CSV file contains rows missing a required field "well_name_point_id"')
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-required.csv")


@then("the response includes validation errors for all rows missing required fields")
def step_impl(context: Context):
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
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "row" in error, "Expected validation error to include row number"
        assert "field" in error, "Expected validation error to include field name"


@then("no wells are imported")
def step_impl(context: Context):
    pass


@given('my CSV file contains one or more duplicate "well_name_point_id" values')
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-duplicate.csv")


@then("the response includes validation errors indicating duplicated values")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])

    print("adssaf", validation_errors)
    print("ffff", response_json)
    assert len(validation_errors) == 1, "Expected 1 validation error"

    error_fields = [
        e["row"] for e in validation_errors if e["field"] == "well_name_point_id"
    ]
    assert error_fields == [2], f"Expected duplicated values for row {error_fields}"
    assert (
        validation_errors[0]["error"] == "Duplicate value for well_name_point_id"
    ), "Expected duplicated values for row 2"


@then("each error identifies the row and field")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "row" in error, "Expected validation error to include row number"
        assert "field" in error, "Expected validation error to include field name"


@then("the response includes validation errors identifying the invalid field and row")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    for error in validation_errors:
        assert "field" in error, "Expected validation error to include field name"
        assert "error" in error, "Expected validation error to include error message"


@given(
    'my CSV file contains invalid lexicon values for "contact_role" or other lexicon fields'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-lexicon.csv")


@given('my CSV file contains invalid ISO 8601 date values in the "date_time" field')
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-date.csv")


@given(
    'my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "utm_easting"'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-numeric.csv")


@given("my CSV file contains column headers but no data rows")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-no-data-headers.csv")


@given("my CSV file is empty")
def step_impl(context: Context):
    # context.file_content = ""
    # context.rows = []
    # context.file_type = "text/csv"
    _set_file_content(context, "well-inventory-empty.csv")


@given("I have a non-CSV file")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-filetype.txt")


@then("the response includes an error message indicating unsupported file type")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "error" in response_json, "Expected response to include an error message"
    assert (
        "Unsupported file type" in response_json["error"]
    ), "Expected error message to indicate unsupported file type"


@then("the response includes an error message indicating an empty file")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "error" in response_json, "Expected response to include an error message"
    assert (
        "Empty file" in response_json["error"]
    ), "Expected error message to indicate an empty file"


@then("the response includes an error indicating that no data rows were found")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "error" in response_json, "Expected response to include an error message"
    assert (
        "No data rows found" in response_json["error"]
    ), "Expected error message to indicate no data rows were found"


@given(
    'my CSV file contains a row with a contact but is missing the required "contact_role" field for that contact'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-contact-role.csv")


@then(
    'the response includes a validation error indicating the missing "contact_role" field'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing contact_role"
    assert (
        validation_errors[0]["error"]
        == "Value error, Role must be provided if name is provided"
    ), "Expected missing contact_role error message"


# @given(
#     "the system has valid lexicon values for contact_role, contact_type, phone_type, email_type, address_type, elevation_method, well_pump_type, well_purpose, well_hole_status, and monitoring_frequency"
# )
# def step_impl_valid_lexicon_values(context: Context):
#     pass
#
#
# @given(
#     "my CSV file contains multiple rows of well inventory data with the following fields"
# )
# def step_impl_csv_file_contains_multiple_rows(context: Context):
#     """Sets up the CSV file with multiple rows of well inventory data."""
#     context.rows = [row.as_dict() for row in context.table]
#     # convert to csv content
#     keys = context.rows[0].keys()
#     nrows = [",".join(keys)]
#     for row in context.rows:
#         nrow = ",".join([row[k] for k in keys])
#         nrows.append(nrow)
#
#     context.file_content = "\n".join(nrows)
#
#
# @when("I upload the CSV file to the bulk upload endpoint")
# def step_impl_upload_csv_file(context: Context):
#     """Uploads the CSV file to the bulk upload endpoint."""
#     # Simulate uploading the CSV file to the bulk upload endpoint
#     context.response = context.client.post(
#         "/bulk-upload/well-inventory",
#         files={"file": ("well_inventory.csv", context.file_content, "text/csv")},
#     )
#
#
# @then(
#     "null values in the response should be represented as JSON null (not placeholder strings)"
# )
# def step_impl_null_values_as_json_null(context: Context):
#     """Verifies that null values in the response are represented as JSON null."""
#     response_json = context.response.json()
#     for record in response_json:
#         for key, value in record.items():
#             if value is None:
#                 assert (
#                     value is None
#                 ), f"Expected JSON null for key '{key}', but got '{value}'"
#

#
# @given('the field "project" is provided')
# def step_impl_project_is_provided(context: Context):
#     assert 'project' in context.header, 'Missing required header: project'
#
#
# @given('the field "well_name_point_id" is provided and unique per row')
# def step_impl(context: Context):
#     assert 'well_name_point_id' in context.header, 'Missing required header: well_name_point_id'
#
#
# @given('the field "site_name" is provided')
# def step_impl(context: Context):
#     assert 'site_name' in context.header, 'Missing required header: site_name'
#
#
# @given('the field "date_time" is provided as a valid timestamp in ISO 8601 format with timezone offset (UTC-8) such as "2025-02-15T10:30:00-08:00"')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
#
# @given('the field "field_staff" is provided and contains the first and last name of the primary person who measured or logged the data')
# def step_impl(context: Context):
#     assert 'field_staff' in context.header, 'Missing required header: field_staff'
#
#
# @given('the field "field_staff_2" is included if available')
# def step_impl(context: Context):
#     assert 'field_staff_2' in context.header, 'Missing required header: field_staff_2'
#
#
# @given('the field "field_staff_3" is included if available')
# def step_impl(context: Context):
#     assert 'field_staff_3' in context.header, 'Missing required header: field_staff_3'
#
#
# @given('the field "contact_name" is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_organization" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_role" is provided and one of the contact_role lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_type" is provided and one of the contact_type lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# # Phone and Email fields are optional
# @given('the field "contact_phone_1" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_phone_1_type" is included if contact_phone_1 is provided and is one of the phone_type '
#        'lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_phone_2" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_phone_2_type" is included if contact_phone_2 is provided and is one of the phone_type '
#        'lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_email_1" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_email_1_type" is included if contact_email_1 is provided and is one of the email_type '
#        'lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_email_2" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_email_2_type" is included if contact_email_2 is provided and is one of the email_type '
#        'lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
#
# # Address fields are optional
# @given('the field "contact_address_1_line_1" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_1_line_2" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_1_type" is included if contact_address_1_line_1 is provided and is one of the address_type lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_address_1_state" is included if contact_address_1_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_1_city" is included if contact_address_1_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_1_postal_code" is included if contact_address_1_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_2_line_1" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_2_line_2" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_2_type" is included if contact_address_2_line_1 is provided and is one of the address_type lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "contact_address_2_state" is included if contact_address_2_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_2_city" is included if contact_address_2_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "contact_address_2_postal_code" is included if contact_address_2_line_1 is provided')
# def step_impl(context: Context):
#     raise StepNotImplementedError
#
# @given('the field "directions_to_site" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "specific_location_of_well" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "repeat_measurement_permission" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "sampling_permission" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "datalogger_installation_permission" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "public_availability_acknowledgement" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "special_requests" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "utm_easting" is provided as a numeric value in NAD83')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "utm_northing" is provided as a numeric value in NAD83')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "utm_zone" is provided as a numeric value')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "elevation_ft" is provided as a numeric value in NAVD88')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "elevation_method" is provided and one of the elevation_method lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "ose_well_record_id" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "date_drilled" is included if available as a valid date in ISO 8601 format with timezone offset ('
#        'UTC-8) such as "2025-02-15T10:30:00-08:00"')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "completion_source" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "total_well_depth_ft" is included if available as a numeric value in feet')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "historic_depth_to_water_ft" is included if available as a numeric value in feet')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "depth_source" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "well_pump_type" is included if available and one of the well_pump_type lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "well_pump_depth_ft" is included if available as a numeric value in feet')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "is_open" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "datalogger_possible" is included if available as true or false')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "casing_diameter_ft" is included if available as a numeric value in feet')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "measuring_point_height_ft" is provided as a numeric value in feet')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "measuring_point_description" is included if available')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "well_purpose" is included if available and one of the well_purpose lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "well_hole_status" is included if available and one of the well_hole_status lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
# @given('the field "monitoring_frequency" is included if available and one of the monitoring_frequency lexicon values')
# def step_impl(context: Context):
#     raise StepNotImplementedError
