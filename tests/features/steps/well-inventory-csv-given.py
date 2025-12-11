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
import csv
from io import StringIO
from pathlib import Path

import pandas as pd
from behave import given
from behave.runner import Context


def _set_file_content(context: Context, name):
    path = Path("tests") / "features" / "data" / name
    context.file_path = path
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


@given(
    'my CSV file contains a row with a contact but is missing the required "contact_role" field for that contact'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-contact-role.csv")


@given(
    "my CSV file contains a row  that has an invalid postal code format in contact_1_address_1_postal_code"
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-postal-code.csv")


@given("a valid CSV file for bulk well inventory upload")
def step_impl_valid_csv_file(context: Context):
    _set_file_content(context, "well-inventory-valid.csv")


@given('my CSV file contains rows missing a required field "well_name_point_id"')
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-required.csv")


@given('my CSV file contains one or more duplicate "well_name_point_id" values')
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-duplicate.csv")


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


@given("my CSV file contains multiple rows of well inventory data")
def step_impl_csv_file_contains_multiple_rows(context: Context):
    """Sets up the CSV file with multiple rows of well inventory data."""
    assert len(context.rows) > 0, "CSV file contains no data rows"


@given("my CSV file is encoded in UTF-8 and uses commas as separators")
def step_impl_csv_file_is_encoded_utf8(context: Context):
    """Sets the CSV file encoding to UTF-8 and sets the CSV separator to commas."""
    # context.csv_file.encoding = 'utf-8'
    # context.csv_file.separator = ','
    # determine the separator from the file content
    sample = context.file_content[:1024]
    dialect = csv.Sniffer().sniff(sample)
    assert dialect.delimiter == ","


@given(
    "my CSV file contains a row with a contact with a phone number that is not in the valid format"
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-phone-number.csv")


@given(
    "my CSV file contains a row with a contact with an email that is not in the valid format"
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-email.csv")


@given(
    'my CSV file contains a row with a contact but is missing the required "contact_type" field for that contact'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-contact-type.csv")


@given(
    'my CSV file contains a row with a contact_type value that is not in the valid lexicon for "contact_type"'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-contact-type.csv")


@given(
    'my CSV file contains a row with a contact with an email but is missing the required "email_type" field for that email'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-email-type.csv")


@given(
    'my CSV file contains a row with a contact with a phone but is missing the required "phone_type" field for that phone'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-phone-type.csv")


@given(
    'my CSV file contains a row with a contact with an address but is missing the required "address_type" field for that address'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-missing-address-type.csv")


@given(
    "my CSV file contains a row with utm_easting utm_northing and utm_zone values that are not within New Mexico"
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-utm.csv")


@given(
    'my CSV file contains invalid ISO 8601 date values in the "date_time" or "date_drilled" field'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-date-format.csv")


@given("my CSV file contains all required headers but in a different column order")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-valid-reordered.csv")


@given("my CSV file contains extra columns but is otherwise valid")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-valid-extra-columns.csv")


@given(
    'my CSV file contains 3 rows of data with 2 valid rows and 1 row missing the required "well_name_point_id"'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-partial.csv")


@given('my CSV file contains a row missing the required "{required_field}" field')
def step_impl(context, required_field):
    _set_file_content(context, "well-inventory-valid.csv")

    df = pd.read_csv(context.file_path, dtype={"contact_2_address_1_postal_code": str})
    df = df.drop(required_field, axis=1)

    buffer = StringIO()
    df.to_csv(buffer, index=False)

    context.file_content = buffer.getvalue()
    context.rows = list(csv.DictReader(context.file_content.splitlines()))


@given(
    'my CSV file contains a row with an invalid boolean value "maybe" in the "is_open" field'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-invalid-boolean-value-maybe.csv")


@given("my CSV file contains a valid but duplicate header row")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-duplicate-header.csv")


@given(
    'my CSV file header row contains the "contact_1_email_1" column name more than once'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-duplicate-columns.csv")


def _get_valid_df(context: Context) -> pd.DataFrame:
    _set_file_content(context, "well-inventory-valid.csv")
    df = pd.read_csv(context.file_path, dtype={"contact_2_address_1_postal_code": str})
    return df


def _set_content_from_df(context: Context, df: pd.DataFrame, delimiter: str = ","):
    buffer = StringIO()
    df.to_csv(buffer, index=False, sep=delimiter)
    context.file_content = buffer.getvalue()
    context.rows = list(csv.DictReader(context.file_content.splitlines()))


@given("my CSV file contains more rows than the configured maximum for bulk upload")
def step_impl(context: Context):
    df = _get_valid_df(context)

    df = pd.concat([df.iloc[:2]] * 1001, ignore_index=True)

    _set_content_from_df(context, df)


@given("my file is named with a .csv extension")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-valid.csv")


@given(
    'my file uses "{delimiter_description}" as the field delimiter instead of commas'
)
def step_impl(context, delimiter_description: str):
    df = _get_valid_df(context)

    if delimiter_description == "semicolons":
        delimiter = ";"
    else:
        delimiter = "\t"

    context.delimiter = delimiter
    _set_content_from_df(context, df, delimiter=delimiter)


@given("my CSV file header row contains all required columns")
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-valid.csv")


@given(
    'my CSV file contains a data row where the "site_name" field value includes a comma and is enclosed in quotes'
)
def step_impl(context: Context):
    _set_file_content(context, "well-inventory-valid-comma-in-quotes.csv")


@given(
    "my CSV file contains a data row where a field begins with a quote but does not have a matching closing quote"
)
def step_impl(context: Context):
    df = _get_valid_df(context)
    df.loc[0]["well_name_point_id"] = '"well-name-point-id'
    _set_content_from_df(context, df)


@given(
    'my CSV file contains all valid columns but uses "XY-" prefix for well_name_point_id values'
)
def step_impl(context: Context):
    df = _get_valid_df(context)
    df["well_name_point_id"] = df["well_name_point_id"].apply(lambda x: "XY-")

    # change contact name
    df.loc[0, "contact_1_name"] = "Contact 1"
    df.loc[0, "contact_2_name"] = "Contact 2"
    df.loc[1, "contact_1_name"] = "Contact 3"

    _set_content_from_df(context, df)


@given(
    "my csv file contains a row where some but not all water level entry fields are filled"
)
def step_impl(context):
    _set_file_content(context, "well-inventory-missing-wl-fields.csv")


# ============= EOF =============================================
