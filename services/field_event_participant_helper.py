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
Field event participant persistence shared by the CSV importers.

``domain/field_staff.py`` holds the rules that need no database -- which column
is the lead, what a new staff contact looks like. This module holds the half
that does: turning those names into ``FieldEventParticipant`` rows and picking
the one that collected a sample. Both importers read the same staff columns, so
keeping the persistence here stops the water level and well inventory paths from
drifting the way they already did once, when only one of them set
``Sample.field_event_participant_id``.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db import Contact, FieldEvent, FieldEventParticipant
from domain.field_staff import (
    FIELD_STAFF_ORGANIZATION,
    LEAD_ROLE,
    field_staff_contact_payload,
)
from services.contact_helper import add_contact


def get_or_create_field_staff_contact(
    session: Session, staff_name: str, user=None
) -> Contact:
    """Resolve or create the contact record used by field event participants."""
    # Contact uniqueness is enforced on (name, organization), so the lookup
    # must use the same key to avoid missing an existing row with a different
    # contact_type and attempting a duplicate insert.
    contact = session.scalars(
        select(Contact)
        .where(Contact.name == staff_name)
        .where(Contact.organization == FIELD_STAFF_ORGANIZATION)
    ).first()

    if contact is None:
        contact = add_contact(
            session, field_staff_contact_payload(staff_name), user, commit=False
        )

    return contact


def ensure_field_event_participants(
    session: Session,
    field_event: FieldEvent,
    staff_entries: tuple[tuple[str, str], ...],
    user=None,
) -> list[FieldEventParticipant]:
    """
    Return event participants for imported staff names, creating any missing ones.

    ``staff_entries`` is the ``(name, role)`` sequence from
    ``domain.field_staff.field_staff_entries``.
    """
    existing_participants = list(
        session.scalars(
            select(FieldEventParticipant)
            .options(selectinload(FieldEventParticipant.participant))
            .where(FieldEventParticipant.field_event_id == field_event.id)
            .order_by(FieldEventParticipant.id.asc())
        ).all()
    )

    for staff_name, role in staff_entries:
        contact = get_or_create_field_staff_contact(session, staff_name, user)
        participant = next(
            (
                existing
                for existing in existing_participants
                if existing.contact_id == contact.id
                and existing.participant_role == role
            ),
            None,
        )
        if participant is None:
            participant = FieldEventParticipant(
                field_event=field_event,
                contact_id=contact.id,
                participant_role=role,
            )
            session.add(participant)
            # Attach the resolved contact eagerly so downstream matching can use
            # participant.participant.name without an extra lookup.
            participant.participant = contact
            existing_participants.append(participant)

    return existing_participants


def resolve_measuring_participant(
    sampler: str, participants: list[FieldEventParticipant]
) -> FieldEventParticipant:
    """Return the unique participant matching ``sampler`` or raise a row error."""
    # Compare on stripped names: the well inventory reader hands the row's
    # values through unstripped, so " A Lopez" in one column and "A Lopez" in
    # another would otherwise fail a row over nothing.
    sampler = sampler.strip()
    matching_participants = [
        participant
        for participant in participants
        if participant.participant is not None
        and participant.participant.name.strip() == sampler
    ]
    if len(matching_participants) == 1:
        return matching_participants[0]

    if not matching_participants:
        raise ValueError(
            "measuring_person "
            f"'{sampler}' could not be matched to a field event participant"
        )

    raise ValueError(
        "measuring_person "
        f"'{sampler}' matched multiple field event participants; "
        # Ambiguous staff rows should fail so the importer never guesses which
        # participant performed the measurement.
        "field_staff values must identify exactly one measuring person"
    )


def lead_participant(
    participants: list[FieldEventParticipant],
) -> FieldEventParticipant | None:
    """
    Return the participant from the ``field_staff`` column, if there is one.

    Only for formats where the measuring person column is optional. A row that
    names staff but no measurer still has one identifiable collector -- the lead
    -- so the sample is linked to them rather than left orphaned.
    """
    leads = [
        participant
        for participant in participants
        if participant.participant_role == LEAD_ROLE
    ]
    if len(leads) == 1:
        return leads[0]
    return None


# ============= EOF =============================================
