from datetime import datetime

from behave import given, when, then
from behave.runner import Context


@given("valid lexicon values exist for:")
def step_impl_valid_lexicon_values(context: Context):
    for row in context.table:
        response = context.client.get(
            "/lexicon/category",
            params={"name": row[0]},
        )
        assert response.status_code == 200, f"Invalid lexicon category: {row[0]}"


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
    response_json = context.response.json()
    wells = response_json.get("wells", [])
    assert len(wells) == 0, "Expected no wells to be imported"


@then("the response includes validation errors indicating duplicated values")
def step_impl(context: Context):
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


@then("the response includes an error message indicating unsupported file type")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "Unsupported file type"
    ), "Expected error message to indicate unsupported file type"


@then("the response includes an error message indicating an empty file")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "Empty file"
    ), "Expected error message to indicate an empty file"


@then("the response includes an error indicating that no data rows were found")
def step_impl(context: Context):
    response_json = context.response.json()
    assert "detail" in response_json, "Expected response to include an detail object"
    assert (
        response_json["detail"][0]["msg"] == "No data rows found"
    ), "Expected error message to indicate no data rows were found"


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
        == "Value error, contact_1_role must be provided if name is provided"
    ), "Expected missing contact_1_role error message"


@then(
    "the response includes a validation error indicating the invalid postal code format"
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    print(validation_errors)
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "contact_1_address_1_postal_code"
    ), "Expected invalid postal code field"
    assert (
        validation_errors[0]["error"] == "Value error, Invalid postal code"
    ), "Expected Value error, Invalid postal code"


@then(
    "the response includes a validation error indicating the invalid phone number format"
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "contact_1_phone_1"
    ), "Expected invalid postal code field"
    assert (
        validation_errors[0]["error"]
        == "Value error, Invalid phone number. 55-555-0101"
    ), "Expected Value error, Invalid phone number. 55-555-0101"


@then("the response includes a validation error indicating the invalid email format")
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    print(validation_errors)
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "contact_1_email_1"
    ), "Expected invalid email field"
    assert (
        validation_errors[0]["error"]
        == "Value error, Invalid email format. john.smithexample.com"
    ), "Expected Value error, Invalid email format. john.smithexample.com"


@then(
    'the response includes a validation error indicating the missing "contact_type" value'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    print(validation_errors)
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing contact_type"
    assert (
        validation_errors[0]["error"]
        == "Value error, contact_1_type must be provided if name is provided"
    ), "Expected Value error, contact_1_type must be provided if name is provided"


@then(
    'the response includes a validation error indicating an invalid "contact_type" value'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert validation_errors[0]["field"] == "contact_1_type", "Expected contact_1_type"
    assert (
        validation_errors[0]["error"]
        == "Input should be 'Primary', 'Secondary' or 'Field Event Participant'"
    ), "Expected Input should be 'Primary', 'Secondary' or 'Field Event Participant'"


@then(
    'the response includes a validation error indicating the missing "email_type" value'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    print(validation_errors)
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing email_type"
    assert (
        validation_errors[0]["error"]
        == "Value error, contact_1_email_1_type type must be provided if email is provided"
    ), "Expected Value error, email_1_type must be provided if email is provided"


@then(
    'the response includes a validation error indicating the missing "phone_type" value'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing phone_type"
    assert (
        validation_errors[0]["error"]
        == "Value error, contact_1_phone_1_type must be provided if phone number is provided"
    ), "Expected Value error, phone_1_type must be provided if phone is provided"


@then(
    'the response includes a validation error indicating the missing "address_type" value'
)
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 1, "Expected 1 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing address_type"
    assert (
        validation_errors[0]["error"]
        == "Value error, All contact address fields must be provided"
    ), "Expected Value error, All contact address fields must be provided"


@then("the response includes a validation error indicating the invalid UTM coordinates")
def step_impl(context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert len(validation_errors) == 2, "Expected 2 validation error"
    assert (
        validation_errors[0]["field"] == "composite field error"
    ), "Expected missing address_type"
    assert (
        validation_errors[0]["error"]
        == "Value error, UTM coordinates are outside of the NM"
    ), "Expected Value error, UTM coordinates are outside of the NM"
    assert (
        validation_errors[1]["error"]
        == "Value error, UTM coordinates are outside of the NM"
    ), "Expected Value error, UTM coordinates are outside of the NM"
