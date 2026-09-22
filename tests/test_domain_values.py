# ===============================================================================
# Copyright 2026 ross
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
"""Shared value helpers and field staff rules. No database, no fixtures."""

from datetime import date, datetime
from enum import Enum

import pytest

from domain.field_staff import (
    FIELD_STAFF_CONTACT_TYPE,
    FIELD_STAFF_ORGANIZATION,
    field_staff_contact_payload,
    field_staff_entries,
)
from domain.values import build_notes, enum_value, to_datetime, to_float


class _Method(Enum):
    STEEL_TAPE = "Steel Tape"


# --------------------------------------------------------------------------
# enum_value
# --------------------------------------------------------------------------
def test_enum_value_unwraps_an_enum():
    assert enum_value(_Method.STEEL_TAPE) == "Steel Tape"


def test_enum_value_passes_a_plain_string_through():
    assert enum_value("Steel Tape") == "Steel Tape"


def test_enum_value_without_a_default_returns_falsy_values_unchanged():
    assert enum_value(None) is None
    assert enum_value("") == ""


def test_enum_value_substitutes_the_default_for_falsy_values():
    assert enum_value(None, "Unknown") == "Unknown"
    assert enum_value("", "Unknown") == "Unknown"


def test_enum_value_default_does_not_override_an_enum():
    assert enum_value(_Method.STEEL_TAPE, "Unknown") == "Steel Tape"


# --------------------------------------------------------------------------
# build_notes
# --------------------------------------------------------------------------
def test_build_notes_keeps_order_and_drops_missing_content():
    assert build_notes(
        (
            ("locked gate", "Access"),
            (None, "General"),
            ("call ahead", "Communication"),
        )
    ) == [
        {"content": "locked gate", "note_type": "Access"},
        {"content": "call ahead", "note_type": "Communication"},
    ]


def test_build_notes_keeps_an_empty_string():
    # Only None means "no note"; the importers never filtered on truthiness.
    assert build_notes((("", "General"),)) == [{"content": "", "note_type": "General"}]


def test_build_notes_of_nothing_is_empty():
    assert build_notes(()) == []


# --------------------------------------------------------------------------
# field staff
# --------------------------------------------------------------------------
def test_field_staff_entries_assigns_lead_then_participants():
    assert field_staff_entries("A Lopez", "B Chen", "C Diaz") == (
        ("A Lopez", "Lead"),
        ("B Chen", "Participant"),
        ("C Diaz", "Participant"),
    )


def test_field_staff_entries_drops_blank_columns():
    assert field_staff_entries("A Lopez", None, "") == (("A Lopez", "Lead"),)
    assert field_staff_entries(None, "B Chen", None) == (("B Chen", "Participant"),)
    assert field_staff_entries(None, None, None) == ()


def test_field_staff_contact_payload_uses_the_shared_defaults():
    assert field_staff_contact_payload("A Lopez") == {
        "name": "A Lopez",
        "role": "Technician",
        "organization": FIELD_STAFF_ORGANIZATION,
        "contact_type": FIELD_STAFF_CONTACT_TYPE,
    }


# --- spreadsheet cell coercion, shared by the chemistry ingests ---------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        (12.5, 12.5),
        (3, 3.0),
        ("  7.2 ", 7.2),
        ("not a number", None),
        # Strict by default: a qualifier is meaningful to a lab result, so a
        # value carrying one must not be read as a plain number.
        ("<0.01", None),
        ("1,234", None),
        # A checkbox is not a measurement, and bool is an int subclass.
        (True, None),
    ],
)
def test_to_float_is_strict_by_default(value, expected):
    assert to_float(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("<0.01", 0.01),
        (">5", 5.0),
        ("1,234", 1234.0),
        ("still not a number", None),
    ],
)
def test_to_float_lenient_accepts_what_people_type(value, expected):
    assert to_float(value, lenient=True) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("2025-06-10T12:05:00", datetime(2025, 6, 10, 12, 5)),
        ("2026-03-09 14:04:00", datetime(2026, 3, 9, 14, 4)),
        ("2025-06-10", datetime(2025, 6, 10)),
        ("6/10/2025", datetime(2025, 6, 10)),
        ("6/10/2025 14:04", datetime(2025, 6, 10, 14, 4)),
        (date(2025, 6, 10), datetime(2025, 6, 10)),
        (datetime(2025, 6, 10, 12, 5), datetime(2025, 6, 10, 12, 5)),
        ("last Tuesday", None),
    ],
)
def test_to_datetime_reads_the_layouts_the_spreadsheets_use(value, expected):
    assert to_datetime(value) == expected


def test_to_datetime_only_pads_a_single_digit_hour_when_asked():
    """Padding is opt-in so a strict importer keeps rejecting malformed times."""
    assert to_datetime("2025-06-06T2:15:00") is None
    assert to_datetime("2025-06-06T2:15:00", pad_single_digit_hour=True) == datetime(
        2025, 6, 6, 2, 15
    )


# ============= EOF =============================================
