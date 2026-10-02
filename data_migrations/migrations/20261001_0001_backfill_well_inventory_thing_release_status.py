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
Copy the Location's release status onto every well (Thing) the well inventory
CSV importer left at ``draft``.

The importer turned ``public_availability_acknowledgement`` into a release
status for the Location only. The Thing stayed at the ``CreateWell`` default of
``draft``, and most visibility filters check the Thing, so a well stayed hidden
even when its owner had agreed to make it public. The importer was fixed to set
the same status on both; this corrects the Things it already created.

Things are identified by provenance, as in
``20260914_0001_convert_well_inventory_casing_diameter``: the importer stamps a
``FieldActivity`` with ``activity_type = 'well inventory'`` on every well it
creates. Only Things still at ``draft`` whose current Location is ``public`` or
``private`` are changed. A Thing someone has already moved off ``draft`` keeps
its status, and a ``draft`` Location has nothing to copy.

A Thing someone set back to ``draft`` on purpose is overwritten too: nothing
here tries to tell it apart from one the importer left there. Review the change
report the dry run writes before applying.

There is no CUTOFF, unlike the casing diameter migration. Copying a status is
safe to repeat, and Things imported after the fix already match their Location,
so they fall out of the selector on their own.

The current Location is resolved with ``Thing.current_location``, the same
property the API uses, so the migration and the app agree on which Location a
Thing is at.

Things are mutated by attribute assignment rather than a bulk Core
``update()``. ``Thing`` is SQLAlchemy-Continuum versioned, and Continuum only
writes ``thing_version`` rows from the Session's unit of work. That history is
the only record of the old values, and therefore the reversal path.

There is no reverse migration. To undo, write a second narrow migration setting
the same Things back to ``draft``, cross-checked against ``thing_version`` and
the change report. Do not use Continuum's ``.revert()``: it restores every
versioned column on the row, not just this one.

Review the dry run before applying:

    oco data-migrations run 20261001_0001_backfill_well_inventory_thing_release_status --dry-run
    oco data-migrations run 20261001_0001_backfill_well_inventory_thing_release_status
    oco data-migrations status
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.field import FieldActivity, FieldEvent
from db.thing import Thing
from transfers.logger import logger

# The activity type the well inventory importer stamps on every well it creates.
WELL_INVENTORY_ACTIVITY_TYPE = "well inventory"
WELL_THING_TYPE = "water well"

DRAFT = "draft"
# Kept local rather than imported from domain.wells: a migration must reproduce
# the rule it ran with, and cannot track a moving import.
COPYABLE_STATUSES = ("public", "private")

REPORT_DIR = Path("reports")


@dataclass(frozen=True)
class PlannedChange:
    thing_id: int
    well_name: str
    location_id: int
    before: str
    after: str


def _plan(session: Session) -> list[PlannedChange]:
    """Read-only. The Things to change, with their before and after statuses."""
    things = session.scalars(
        select(Thing)
        .join(FieldEvent, FieldEvent.thing_id == Thing.id)
        .join(FieldActivity, FieldActivity.field_event_id == FieldEvent.id)
        .where(
            FieldActivity.activity_type == WELL_INVENTORY_ACTIVITY_TYPE,
            Thing.thing_type == WELL_THING_TYPE,
            Thing.release_status == DRAFT,
        )
        .distinct()
        .order_by(Thing.id.asc())
    ).all()

    changes = []
    for thing in things:
        location = thing.current_location
        if location is None or location.release_status not in COPYABLE_STATUSES:
            continue
        changes.append(
            PlannedChange(
                thing_id=thing.id,
                well_name=thing.name,
                location_id=location.id,
                before=thing.release_status,
                after=location.release_status,
            )
        )
    return changes


def _write_change_report(changes: list[PlannedChange]) -> Path:
    """Write what changed to a timestamped CSV.

    This is a plain filesystem write, not part of the database transaction: it
    is NOT undone by session.rollback(). That is deliberate during a dry run,
    where the report is the durable artifact you are left with after the
    database changes are discarded, but it does mean every dry run leaves its
    own file behind, hence the timestamp in the name.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H_%M_%S")
    path = REPORT_DIR / f"backfill_thing_release_status_{stamp}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "well_name",
                "thing_id",
                "location_id",
                "release_status_before",
                "release_status_after",
            ],
        )
        writer.writeheader()
        for change in changes:
            writer.writerow(
                {
                    "well_name": change.well_name,
                    "thing_id": change.thing_id,
                    "location_id": change.location_id,
                    "release_status_before": change.before,
                    "release_status_after": change.after,
                }
            )
    return path


def _log_plan(changes: list[PlannedChange], report: Path) -> None:
    for change in changes:
        logger.info(
            "  %-20s id=%-7s %s -> %s",
            change.well_name,
            change.thing_id,
            change.before,
            change.after,
        )
    if changes:
        counts = Counter(change.after for change in changes)
        logger.info(
            "thing release status - %d Things: %d to public, %d to private",
            len(changes),
            counts["public"],
            counts["private"],
        )
    else:
        logger.warning("thing release status - no Things matched; nothing to copy")
    logger.info("thing release status - change report: %s", report)


def dry_run(session: Session) -> list[PlannedChange]:
    changes = _plan(session)
    _log_plan(changes, _write_change_report(changes))
    return changes


def run(session: Session) -> None:
    changes = _plan(session)
    report = _write_change_report(changes)
    _log_plan(changes, report)

    if not changes:
        return None

    by_id = {c.thing_id: c for c in changes}
    things = session.scalars(select(Thing).where(Thing.id.in_(by_id.keys()))).all()

    # Guard against the set shifting between planning and loading; a partial
    # apply would leave the change report describing rows that never changed.
    if len(things) != len(changes):
        raise ValueError(
            f"expected {len(changes)} Things to change, loaded {len(things)}"
        )

    for thing in things:
        thing.release_status = by_id[thing.id].after

    session.flush()

    unchanged = [
        thing.name for thing in things if thing.release_status != by_id[thing.id].after
    ]
    if unchanged:
        raise ValueError(f"Things not changed after flush: {', '.join(unchanged)}")

    logger.info(
        "thing release status - copied onto %d Things; change report: %s",
        len(things),
        report,
    )
    return None


MIGRATION = DataMigration(
    id="20261001_0001_backfill_well_inventory_thing_release_status",
    alembic_revision="a3b4c5d6e7f8",
    name="Backfill well inventory Thing release status from its Location",
    description=(
        "The well inventory CSV importer set the release status from "
        "public_availability_acknowledgement on the Location only, leaving "
        "every Thing it created at draft. Copies the current Location's "
        "public or private status onto Things carrying a 'well inventory' "
        "field activity that are still draft."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
