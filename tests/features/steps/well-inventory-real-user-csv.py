from behave import then
from behave.runner import Context


@then("the response summary reports all rows were processed from the source CSV")
def step_impl(context: Context):
    response_json = context.response.json()
    summary = response_json.get("summary", {})
    assert (
        summary.get("total_rows_processed") == context.row_count
    ), "Expected total_rows_processed to match CSV row count"


@then("the response summary includes import and validation counts")
def step_impl(context: Context):
    response_json = context.response.json()
    summary = response_json.get("summary", {})
    assert "total_rows_imported" in summary, "Expected total_rows_imported in summary"
    assert (
        "validation_errors_or_warnings" in summary
    ), "Expected validation_errors_or_warnings in summary"


@then("the command exit code matches whether validation errors were reported")
def step_impl(context: Context):
    response_json = context.response.json()
    has_validation_errors = bool(response_json.get("validation_errors"))
    if has_validation_errors:
        assert (
            context.cli_result.exit_code != 0
        ), "Expected non-zero exit code when validation errors exist"
    else:
        assert (
            context.cli_result.exit_code == 0
        ), "Expected zero exit code when validation errors do not exist"


@then("the response includes one or more validation errors")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert validation_errors, "Expected one or more validation errors"


@then("each validation error contains row field and error details")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    assert validation_errors, "Expected one or more validation errors"
    for error in validation_errors:
        assert "row" in error, "Expected validation error to include row"
        assert "field" in error, "Expected validation error to include field"
        assert "error" in error, "Expected validation error to include error"


@then("no wells are imported when validation errors are present")
def step_impl(context: Context):
    response_json = context.response.json()
    validation_errors = response_json.get("validation_errors", [])
    wells = response_json.get("wells", [])
    if validation_errors:
        assert wells == [], "Expected no wells to be imported when errors are present"
