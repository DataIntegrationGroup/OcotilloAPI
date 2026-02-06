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
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.location import Location
from db.notes import Notes

NOTE_TYPE = "General"
BATCH_SIZE = 1000


def _iter_location_notes(session: Session):
    stmt = select(
        Location.id,
        Location.nma_location_notes,
        Location.release_status,
    ).where(Location.nma_location_notes.isnot(None))
    for row in session.execute(stmt):
        note = (row.nma_location_notes or "").strip()
        if not note:
            continue
        yield row.id, note, row.release_status


def run(session: Session) -> None:
    buffer: list[tuple[int, str, str]] = []
    for item in _iter_location_notes(session):
        buffer.append(item)
        if len(buffer) >= BATCH_SIZE:
            _flush_batch(session, buffer)
            buffer.clear()
    if buffer:
        _flush_batch(session, buffer)


def _flush_batch(session: Session, batch: list[tuple[int, str, str]]) -> None:
    location_ids = [row[0] for row in batch]
    existing = session.execute(
        select(Notes.target_id, Notes.content).where(
            Notes.target_table == "location",
            Notes.note_type == NOTE_TYPE,
            Notes.target_id.in_(location_ids),
        )
    ).all()
    existing_set = {(row.target_id, row.content) for row in existing}

    inserts = []
    for location_id, note, release_status in batch:
        if (location_id, note) in existing_set:
            continue
        inserts.append(
            {
                "target_id": location_id,
                "target_table": "location",
                "note_type": NOTE_TYPE,
                "content": note,
                "release_status": release_status or "draft",
            }
        )

    if inserts:
        session.execute(insert(Notes), inserts)

    session.execute(
        update(Location)
        .where(Location.id.in_(location_ids))
        .values(nma_location_notes=None)
    )
    session.commit()


MIGRATION = DataMigration(
    id="20260205_0001_move_nma_location_notes",
    alembic_revision="f0c9d8e7b6a5",
    name="Move NMA location notes to Notes table",
    description="Backfill polymorphic notes from Location.nma_location_notes.",
    run=run,
    is_repeatable=False,
)
