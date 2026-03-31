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

from types import SimpleNamespace
from uuid import uuid4

from db import ThingContactAssociation, Thing, Notes, Contact
from db.engine import session_ctx
from transfers.contact_transfer import ContactTransfer, _add_first_contact
from transfers.well_transfer import WellTransferer


def _run_contact_transfer(pointids: list[str]):
    wt = WellTransferer(pointids=pointids)
    wt.transfer_parallel()

    ct = ContactTransfer(pointids=pointids)
    ct.transfer()


def test_multiple_wells():
    pointids = ["MG-022", "MG-030", "MG-043"]
    _run_contact_transfer(pointids)

    with session_ctx() as sess:
        assert sess.query(ThingContactAssociation).count() == 6


def test_owner_comment_creates_notes_for_primary_only():
    point_id = "MG-043"
    _run_contact_transfer([point_id])

    with session_ctx() as sess:
        thing = sess.query(Thing).filter(Thing.name == point_id).one()
        contacts = {
            assoc.contact.contact_type: assoc.contact
            for assoc in thing.contact_associations
        }

        primary = contacts.get("Primary")
        secondary = contacts.get("Secondary")

        assert primary is not None
        assert secondary is not None

        primary_notes = (
            sess.query(Notes)
            .filter_by(target_id=primary.id, target_table="contact")
            .all()
        )
        assert len(primary_notes) == 1
        assert primary_notes[0].note_type == "OwnerComment"

        secondary_notes = (
            sess.query(Notes)
            .filter_by(target_id=secondary.id, target_table="contact")
            .all()
        )
        assert secondary_notes == []


def test_owner_comment_absent_skips_notes():
    point_id = "MG-016"
    _run_contact_transfer([point_id])

    with session_ctx() as sess:
        thing = sess.query(Thing).filter(Thing.name == point_id).one()
        contact_ids = [assoc.contact.id for assoc in thing.contact_associations]

        assert contact_ids, "Expected at least one contact for MG-016"

        note_count = (
            sess.query(Notes)
            .filter(Notes.target_table == "contact", Notes.target_id.in_(contact_ids))
            .count()
        )
        assert note_count == 0


def test_ownerkey_fallback_name_when_name_and_org_missing(water_well_thing):
    with session_ctx() as sess:
        thing = sess.get(Thing, water_well_thing.id)
        contact_by_owner_type = {}
        contact_by_name_org = {}
        row = SimpleNamespace(
            FirstName=None,
            LastName=None,
            OwnerKey="Fallback OwnerKey Name",
            Email=None,
            CtctPhone=None,
            Phone=None,
            CellPhone=None,
            StreetAddress=None,
            Address2=None,
            City=None,
            State=None,
            Zip=None,
            MailingAddress=None,
            MailCity=None,
            MailState=None,
            MailZipCode=None,
            PhysicalAddress=None,
            PhysicalCity=None,
            PhysicalState=None,
            PhysicalZipCode=None,
        )

        # Should not raise "Either name or organization must be provided."
        contact = _add_first_contact(
            sess,
            row=row,
            thing=thing,
            organization=None,
            added=set(),
            contact_by_owner_type=contact_by_owner_type,
            contact_by_name_org=contact_by_name_org,
        )
        sess.flush()

        assert contact is not None
        assert contact.name == "Fallback OwnerKey Name-primary"
        assert contact.organization is None


def test_ownerkey_dedupes_when_fallback_name_differs(water_well_thing):
    owner_key = f"OwnerKey-{uuid4()}"
    with session_ctx() as sess:
        first_thing = sess.get(Thing, water_well_thing.id)
        contact_by_owner_type = {}
        contact_by_name_org = {}
        second_thing = Thing(
            name=f"Second Well {uuid4()}",
            thing_type="water well",
            release_status="draft",
        )
        sess.add(second_thing)
        sess.flush()

        complete_row = SimpleNamespace(
            FirstName="Casey",
            LastName="Owner",
            OwnerKey=owner_key,
            Email=None,
            CtctPhone=None,
            Phone=None,
            CellPhone=None,
            StreetAddress=None,
            Address2=None,
            City=None,
            State=None,
            Zip=None,
            MailingAddress=None,
            MailCity=None,
            MailState=None,
            MailZipCode=None,
            PhysicalAddress=None,
            PhysicalCity=None,
            PhysicalState=None,
            PhysicalZipCode=None,
        )
        fallback_row = SimpleNamespace(
            FirstName=None,
            LastName=None,
            OwnerKey=owner_key,
            Email=None,
            CtctPhone=None,
            Phone=None,
            CellPhone=None,
            StreetAddress=None,
            Address2=None,
            City=None,
            State=None,
            Zip=None,
            MailingAddress=None,
            MailCity=None,
            MailState=None,
            MailZipCode=None,
            PhysicalAddress=None,
            PhysicalCity=None,
            PhysicalState=None,
            PhysicalZipCode=None,
        )

        added = set()
        first_contact = _add_first_contact(
            sess,
            row=complete_row,
            thing=first_thing,
            organization=None,
            added=added,
            contact_by_owner_type=contact_by_owner_type,
            contact_by_name_org=contact_by_name_org,
        )
        assert first_contact is not None
        assert first_contact.name == "Casey Owner"

        second_contact = _add_first_contact(
            sess,
            row=fallback_row,
            thing=second_thing,
            organization=None,
            added=added,
            contact_by_owner_type=contact_by_owner_type,
            contact_by_name_org=contact_by_name_org,
        )
        sess.flush()

        # Reused existing contact; no duplicate fallback-name contact created.
        assert second_contact is None
        contacts = (
            sess.query(Contact)
            .filter(
                Contact.nma_pk_owners == owner_key,
                Contact.contact_type == "Primary",
            )
            .all()
        )
        assert len(contacts) == 1
        assert contacts[0].name == "Casey Owner"

        assoc_count = (
            sess.query(ThingContactAssociation)
            .filter(ThingContactAssociation.contact_id == contacts[0].id)
            .count()
        )
        assert assoc_count == 2


# ============= EOF =============================================
