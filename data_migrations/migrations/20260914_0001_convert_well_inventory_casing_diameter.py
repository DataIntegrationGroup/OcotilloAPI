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
Convert ``thing.well_casing_diameter`` from feet to inches for every well the
well inventory CSV importer created.

The importer read a CSV column named ``casing_diameter_ft`` and wrote it
straight into ``thing.well_casing_diameter``, which is declared inches
(``db/thing.py``: ``info={"unit": "inches"}``). Every well it created therefore
carries a diameter 12x too small, and the API labels the value "in" regardless,
so the wrong number reaches the ``ogc_*`` feature layers. The importer was fixed
to convert on the way in; this corrects the rows it already wrote.

Rows are identified by provenance, not by value. The importer stamps a
``FieldActivity`` with ``activity_type = 'well inventory'`` on every well it
creates, and ``_find_existing_imported_well`` in ``services/well_inventory_csv.py``
already relies on that marker. It separates importer-created wells from wells
entered through the API or migrated from the legacy AMPAPI transfer, both of
which always stored inches correctly.

Every non-null diameter in that set is multiplied by 12. Nothing here tries to
guess which rows field staff may have typed in inches despite the ``_ft``
header: a data entry error stays an error, just scaled. Reviewing the report
this migration writes is how those get found.

**CUTOFF must be the deploy timestamp of the importer fix.** Multiplying by 12
is not idempotent, and the provenance selector does not shrink once the
migration has run, so ``CUTOFF`` is what keeps correctly-imported wells out of
scope forever. Bump it to the real deploy time before running, and run promptly
after the deploy: an import that lands after ``CUTOFF`` but before the fix is
live is wrong *and* excluded, and needs handling by hand.

Wells are loaded as ORM instances and mutated by attribute assignment rather
than through a bulk Core ``update()``. ``Thing`` is SQLAlchemy-Continuum
versioned (``db/thing.py``: ``__versioned__ = {}``), and Continuum builds
``thing_version`` rows from the Session's unit of work at flush time, which
Core-style bulk DML never populates. The ``thing_version`` history is the only
after-the-fact record of the old values, and therefore the reversal path.

There is no reverse migration. To undo, write a second narrow migration
dividing the same set by 12, cross-checked against ``thing_version``. Do not use
Continuum's ``.revert()``: it restores every versioned column on the row, not
just this one.

Review the dry run before applying:

    oco data-migrations run 20260914_0001_convert_well_inventory_casing_diameter --dry-run
    oco data-migrations run 20260914_0001_convert_well_inventory_casing_diameter
    oco data-migrations status
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.field import FieldActivity, FieldEvent
from db.thing import Thing
from transfers.logger import logger

# The activity type the well inventory importer stamps on every well it creates.
WELL_INVENTORY_ACTIVITY_TYPE = "well inventory"
WELL_THING_TYPE = "water well"

# Kept local rather than imported from domain.units for the same reason alembic
# revisions keep their own copy: a migration must reproduce the arithmetic it
# ran with, and cannot track a moving import.
INCHES_PER_FOOT = 12.0

# The deploy timestamp of the importer fix. Wells created at or after this
# moment already hold inches and must never be scaled again. See the module
# docstring before changing it.
CUTOFF = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)

REPORT_DIR = Path("reports")


@dataclass(frozen=True)
class PlannedConversion:
    thing_id: int
    well_name: str
    before: float
    after: float


def _plan(session: Session) -> list[PlannedConversion]:
    """Read-only. The wells to convert, with their before and after values."""
    things = session.scalars(
        select(Thing)
        .join(FieldEvent, FieldEvent.thing_id == Thing.id)
        .join(FieldActivity, FieldActivity.field_event_id == FieldEvent.id)
        .where(
            FieldActivity.activity_type == WELL_INVENTORY_ACTIVITY_TYPE,
            Thing.thing_type == WELL_THING_TYPE,
            Thing.well_casing_diameter.isnot(None),
            Thing.created_at < CUTOFF,
        )
        .distinct()
        .order_by(Thing.id.asc())
    ).all()

    return [
        PlannedConversion(
            thing_id=thing.id,
            well_name=thing.name,
            before=thing.well_casing_diameter,
            after=round(thing.well_casing_diameter * INCHES_PER_FOOT, 6),
        )
        for thing in things
    ]


def _count_excluded_by_cutoff(session: Session) -> int:
    """Wells this migration would convert if CUTOFF were not in the way.

    A stale CUTOFF silently under-selects, and a converted value is
    indistinguishable from a correct one afterwards, so the count is surfaced
    in the dry run rather than left to be noticed later.
    """
    return (
        session.scalar(
            select(func.count()).select_from(
                select(Thing.id)
                .join(FieldEvent, FieldEvent.thing_id == Thing.id)
                .join(FieldActivity, FieldActivity.field_event_id == FieldEvent.id)
                .where(
                    FieldActivity.activity_type == WELL_INVENTORY_ACTIVITY_TYPE,
                    Thing.thing_type == WELL_THING_TYPE,
                    Thing.well_casing_diameter.isnot(None),
                    Thing.created_at >= CUTOFF,
                )
                .distinct()
                .subquery()
            )
        )
        or 0
    )


def _write_change_report(conversions: list[PlannedConversion]) -> Path:
    """Write what changed to a timestamped CSV.

    This is a plain filesystem write, not part of the database transaction: it
    is NOT undone by session.rollback(). That is deliberate during a dry run,
    where the report is the durable artifact you are left with after the
    database changes are discarded, but it does mean every dry run leaves its
    own file behind, hence the timestamp in the name.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H_%M_%S")
    path = REPORT_DIR / f"convert_casing_diameter_{stamp}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "well_name",
                "thing_id",
                "casing_diameter_before",
                "casing_diameter_after",
            ],
        )
        writer.writeheader()
        for conversion in conversions:
            writer.writerow(
                {
                    "well_name": conversion.well_name,
                    "thing_id": conversion.thing_id,
                    "casing_diameter_before": conversion.before,
                    "casing_diameter_after": conversion.after,
                }
            )
    return path


def _log_plan(
    conversions: list[PlannedConversion], report: Path, excluded: int
) -> None:
    logger.info("casing diameter ft to in - cutoff %s", CUTOFF.isoformat())
    for conversion in conversions:
        logger.info(
            "  %-20s id=%-7s %.4f ft -> %.4f in",
            conversion.well_name,
            conversion.thing_id,
            conversion.before,
            conversion.after,
        )
    if conversions:
        befores = [c.before for c in conversions]
        logger.info(
            "casing diameter ft to in - %d wells, source values %.4f to %.4f ft",
            len(conversions),
            min(befores),
            max(befores),
        )
    else:
        logger.warning(
            "casing diameter ft to in - no wells matched; nothing to convert"
        )
    if excluded:
        logger.warning(
            "casing diameter ft to in - %d well(s) created at or after the cutoff "
            "are excluded. If the importer fix was not live by %s, they are still "
            "in feet and need handling by hand.",
            excluded,
            CUTOFF.isoformat(),
        )
    logger.info("casing diameter ft to in - change report: %s", report)


def dry_run(session: Session) -> list[PlannedConversion]:
    conversions = _plan(session)
    _log_plan(
        conversions,
        _write_change_report(conversions),
        _count_excluded_by_cutoff(session),
    )
    return conversions


def run(session: Session) -> None:
    conversions = _plan(session)
    report = _write_change_report(conversions)
    _log_plan(conversions, report, _count_excluded_by_cutoff(session))

    if not conversions:
        return None

    by_id = {c.thing_id: c for c in conversions}
    things = session.scalars(select(Thing).where(Thing.id.in_(by_id.keys()))).all()

    # Guard against the set shifting between planning and loading; a partial
    # apply would be invisible afterwards, since the converted value is
    # indistinguishable from a correct one.
    if len(things) != len(conversions):
        raise ValueError(
            f"expected {len(conversions)} wells to convert, loaded {len(things)}"
        )

    for thing in things:
        thing.well_casing_diameter = by_id[thing.id].after

    session.flush()

    unchanged = [
        thing.name
        for thing in things
        if thing.well_casing_diameter != by_id[thing.id].after
    ]
    if unchanged:
        raise ValueError(f"wells not converted after flush: {', '.join(unchanged)}")

    logger.info(
        "casing diameter ft to in - converted %d wells; change report: %s",
        len(things),
        report,
    )
    return None


MIGRATION = DataMigration(
    id="20260914_0001_convert_well_inventory_casing_diameter",
    alembic_revision="3f9c1b7d2a64",
    name="Convert well inventory casing diameter from feet to inches",
    description=(
        "The well inventory CSV importer wrote its feet-valued "
        "'casing_diameter_ft' column straight into thing.well_casing_diameter, "
        "which stores inches, so every well it created is 12x too small. "
        "Multiplies the diameter by 12 for wells carrying a 'well inventory' "
        "field activity and created before CUTOFF, the deploy timestamp of the "
        "importer fix."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
