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
"""
Field staff rules shared by the CSV importers.

Both importers read the same three fixed staff columns and both create the same
kind of contact for a name they have not seen before. Keeping the roles and the
contact defaults here stops the two from drifting.
"""

LEAD_ROLE = "Lead"
PARTICIPANT_ROLE = "Participant"

FIELD_STAFF_CONTACT_TYPE = "Field Event Participant"
FIELD_STAFF_ORGANIZATION = "NMBGMR"
FIELD_STAFF_CONTACT_ROLE = "Technician"


def field_staff_entries(
    lead: str | None,
    second: str | None,
    third: str | None,
) -> tuple[tuple[str, str], ...]:
    """
    Normalize the three fixed staff columns into ``(name, role)`` pairs.

    The first column is the lead; the other two are participants. Blank columns
    are dropped, so a row that names only a lead yields a single entry.
    """
    specs = (
        (lead, LEAD_ROLE),
        (second, PARTICIPANT_ROLE),
        (third, PARTICIPANT_ROLE),
    )
    return tuple((name, role) for name, role in specs if name)


def field_staff_contact_payload(name: str) -> dict:
    """
    Build the contact payload used when an imported staff name has no contact yet.

    Callers must look the contact up on ``(name, organization)`` -- the pair
    ``Contact`` enforces uniqueness on. Including ``contact_type`` in the lookup
    misses an existing row that was created with a different type and then fails
    on the duplicate insert.
    """
    return {
        "name": name,
        "role": FIELD_STAFF_CONTACT_ROLE,
        "organization": FIELD_STAFF_ORGANIZATION,
        "contact_type": FIELD_STAFF_CONTACT_TYPE,
    }


# ============= EOF =============================================
