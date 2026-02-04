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

from db import ThingContactAssociation, Thing, Notes, Contact
from db.engine import session_ctx
from transfers.contact_transfer import ContactTransfer
from transfers.well_transfer import WellTransferer


def _run_contact_transfer(pointids: list[str]):
    wt = WellTransferer(pointids=pointids)
    wt.transfer()

    ct = ContactTransfer(pointids=pointids)
    ct.transfer()


def test_multiple_wells():
    pointids = ["MG-022", "MG-030", "MG-043"]
    _run_contact_transfer(pointids)

    with session_ctx() as sess:
        assert sess.query(ThingContactAssociation).count() == 6

        sess.query(Thing).delete()
        sess.query(Contact).delete()
        sess.commit()


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

        sess.query(Thing).delete()
        sess.query(Contact).delete()
        sess.commit()


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

        sess.query(Thing).delete()
        sess.query(Contact).delete()
        sess.commit()


# ============= EOF =============================================
