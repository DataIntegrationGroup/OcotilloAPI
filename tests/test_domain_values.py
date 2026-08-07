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

from enum import Enum

from domain.field_staff import (
    FIELD_STAFF_CONTACT_TYPE,
    FIELD_STAFF_ORGANIZATION,
    field_staff_contact_payload,
    field_staff_entries,
)
from domain.values import build_notes, enum_value


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


# ============= EOF =============================================
