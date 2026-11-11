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
Set the release status of groundwater level readings imported by the well
inventory and water level CSV importers, which left every reading at the
``draft`` default (BDMS-1561).

The public EDR ``waterlevels`` collection (``ogc_waterlevels``) shows a reading
only when both the reading and its well are ``public``. Neither importer set
``observation.release_status``, so a public well showed none of its imported
readings. The importers are fixed separately; imports are paused until those
fixes deploy, so one run covers every affected reading and the migration is
not repeatable.

Candidates are ``draft`` groundwater level readings on water wells, reached
through a ``groundwater level`` field activity, with no ``nma_pk_waterlevels``
(that marks a reading transferred from NM_Aquifer, which this does not touch).
Each candidate falls into one source, judged by the footprint each importer
leaves:

* ``well_inventory``: its field event also carries a ``well inventory``
  activity, and its sample is named ``<well name>-WL-<YYYYMMDDHHMM>``, the
  only name that importer has written (it created no readings before
  2026-03-10). The reading takes the well's status, which is the owner's answer
  to "Owner acknowledges data will be publicly available": public stays
  public, private stays private, and a draft well leaves the reading at draft.
* ``water_level_csv``: no ``well inventory`` activity on its event, and a
  sample named ``<well name>-WL-<YYYYMMDDHHMM>`` (since 2026-03-26) or
  ``wl-<uuid>`` (before, ``git show 6a09881a``). The reading takes the
  well's status too, because the owner's decision covers past readings:
  public stays public, private stays private, and a draft well leaves the
  reading at draft. For a well transferred from NM_Aquifer, that status is
  the well's PublicRelease flag, and most NM_Aquifer readings on a private
  well are already private.
* ``unrecognized``: anything else. Never changed, only reported. Expected to be
  empty, since no readings are believed to have been entered by hand; a
  nonzero count is the signal to look before running. A well renamed after its
  import also lands here, the safe direction.

Names must match the whole format, not just a prefix, so a hand-entered sample
that merely starts with ``wl-`` is not mistaken for an import and published.

Two checks guard the changes:

* A reading whose ``observation_version`` history shows any status other than
  ``draft`` is skipped. Someone moved it off draft and back on purpose, and
  that choice outranks the owner's answer. A reading with no version rows at
  all is still changed, but flagged ``history_missing`` and counted in a
  warning, because nothing confirms the importer left it at draft.
* A well inventory well (any field event of the well carries a ``well
  inventory`` activity) with any reading to change, of either source, must
  have the same status as its current Location. The importer set both from the
  same answer, so a difference means one of them was changed afterwards
  (through the API, direct SQL or another migration), and the well's status
  can no longer be taken as the owner's answer. ``dry_run`` reports the
  mismatches; ``run`` raises before changing anything. This cannot catch a
  well and Location edited to the same new status together. Wells that were
  never inventoried are not checked: there is no inventory answer to compare.

Readings are changed by attribute assignment, not a bulk Core ``update()``.
``Observation`` is SQLAlchemy-Continuum versioned, and Continuum only writes
``observation_version`` rows from the Session's unit of work. That history is
the only record of the old values, and so the only way back. The rows are
reloaded with ``FOR UPDATE`` and only while still ``draft``, so a reading
someone changes between planning and applying is caught by the count guard
instead of being overwritten.

There is no reverse migration. To undo, write a second narrow migration that
sets the same readings back to ``draft``, cross-checked against
``observation_version`` and the change report or job log. Do not use
Continuum's ``.revert()``: it restores every versioned column on the row, not
just this one.

The Data Migrations workflow has no dry-run action, so the dry run is a local
CLI run (it writes no ``data_migration_history`` row, so the CLI role is
enough). The real run goes through the workflow with ``action = run``; its
runner keeps the job log but not the CSV report. A workflow ``run-all`` meant
for another migration would apply this one too, without a dry run, so use
``run`` with this id until it has been applied.

    oco data-migrations run 20261110_0001_backfill_imported_water_level_release_status --dry-run
    oco data-migrations status
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session, aliased, selectinload
from sqlalchemy_continuum import version_class

from data_migrations.base import DataMigration
from db.field import FieldActivity, FieldEvent
from db.location import LocationThingAssociation
from db.observation import Observation
from db.parameter import Parameter
from db.sample import Sample
from db.thing import Thing
from transfers.logger import logger

# Kept local rather than imported from domain/ or services/: a migration must
# reproduce the rule it ran with, and cannot track a moving import.
GROUNDWATER_LEVEL_PARAMETER = "groundwater level"
GROUNDWATER_LEVEL_ACTIVITY_TYPE = "groundwater level"
WELL_INVENTORY_ACTIVITY_TYPE = "well inventory"
WELL_THING_TYPE = "water well"
# "<well name>-WL-<YYYYMMDDHHMM>", written by both importers
# (domain.samples.water_level_sample_name). The well name part is matched
# literally, outside the regex.
TIMESTAMPED_NAME_SUFFIX = re.compile(r"-WL-\d{12}")
# "wl-<uuid>", written by the water level importer until 2026-03-26.
UUID_NAME = re.compile(
    r"wl-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)

DRAFT = "draft"
PUBLIC = "public"
PRIVATE = "private"

WELL_INVENTORY = "well_inventory"
WATER_LEVEL_CSV = "water_level_csv"
UNRECOGNIZED = "unrecognized"
SOURCES = (WELL_INVENTORY, WATER_LEVEL_CSV, UNRECOGNIZED)

CHANGE = "change"
SKIP_HISTORY_NON_DRAFT = "skip_history_non_draft"
SKIP_WELL_NOT_RELEASED = "skip_well_not_released"
SKIP_UNRECOGNIZED = "skip_unrecognized"
ABORT_STATUS_MISMATCH = "abort_status_mismatch"

# pg8000 sends each IN value as its own bind parameter and the wire protocol
# caps a statement at 32767, so large id lists go in batches.
ID_BATCH_SIZE = 5000

# Every log line starts with this, so the lines can be found in a long
# workflow job log.
LOG_PREFIX = "BDMS-1561 water level release status:"

REPORT_DIR = Path("reports")


@dataclass(frozen=True)
class PlannedReading:
    observation_id: int
    thing_id: int
    well_name: str
    well_release_status: str
    # True when any field event of the well carries a well inventory activity,
    # which is what subjects the well to the Location check.
    well_inventory_well: bool
    sample_name: str | None
    source: str
    observation_datetime: datetime | None
    before: str
    # Equal to before for every action except change.
    after: str
    action: str
    # True when the reading has no observation_version rows, so its history
    # cannot confirm the importer left it at draft.
    history_missing: bool = False
    # Filled only for abort_status_mismatch, so the report shows both sides of
    # the disagreement without a second query.
    location_release_status: str | None = None


def _batches(ids: list[int]):
    for start in range(0, len(ids), ID_BATCH_SIZE):
        yield ids[start : start + ID_BATCH_SIZE]


def _candidates(session: Session):
    """Read-only. Draft groundwater level readings not transferred from NM_Aquifer."""
    event_activity = aliased(FieldActivity)
    event_has_inventory = exists().where(
        event_activity.field_event_id == FieldEvent.id,
        event_activity.activity_type == WELL_INVENTORY_ACTIVITY_TYPE,
    )
    well_event = aliased(FieldEvent)
    well_activity = aliased(FieldActivity)
    well_has_inventory = exists().where(
        well_event.thing_id == Thing.id,
        well_activity.field_event_id == well_event.id,
        well_activity.activity_type == WELL_INVENTORY_ACTIVITY_TYPE,
    )
    return session.execute(
        select(
            Observation.id,
            Observation.observation_datetime,
            Observation.release_status,
            Sample.sample_name,
            Thing.id,
            Thing.name,
            Thing.release_status,
            event_has_inventory.label("event_has_inventory"),
            well_has_inventory.label("well_has_inventory"),
        )
        .join(
            Parameter,
            and_(
                Parameter.id == Observation.parameter_id,
                Parameter.parameter_name == GROUNDWATER_LEVEL_PARAMETER,
            ),
        )
        .join(Sample, Sample.id == Observation.sample_id)
        .join(
            FieldActivity,
            and_(
                FieldActivity.id == Sample.field_activity_id,
                FieldActivity.activity_type == GROUNDWATER_LEVEL_ACTIVITY_TYPE,
            ),
        )
        .join(FieldEvent, FieldEvent.id == FieldActivity.field_event_id)
        .join(
            Thing,
            and_(Thing.id == FieldEvent.thing_id, Thing.thing_type == WELL_THING_TYPE),
        )
        .where(
            Observation.release_status == DRAFT,
            Observation.nma_pk_waterlevels.is_(None),
        )
        .order_by(Thing.name.asc(), Observation.observation_datetime.asc())
    ).all()


def _is_timestamped_name(sample_name: str | None, well_name: str) -> bool:
    # The well name is compared as a plain prefix, not put into the regex, so
    # characters in it can never act as a pattern.
    if not sample_name or not sample_name.startswith(well_name):
        return False
    return TIMESTAMPED_NAME_SUFFIX.fullmatch(sample_name[len(well_name) :]) is not None


def _is_uuid_name(sample_name: str | None) -> bool:
    return bool(sample_name) and UUID_NAME.fullmatch(sample_name) is not None


def _classify(row) -> PlannedReading:
    (
        observation_id,
        observation_datetime,
        before,
        sample_name,
        thing_id,
        well_name,
        well_status,
        event_has_inventory,
        well_has_inventory,
    ) = row

    def planned(source, after, action):
        return PlannedReading(
            observation_id=observation_id,
            thing_id=thing_id,
            well_name=well_name,
            well_release_status=well_status,
            well_inventory_well=bool(well_has_inventory),
            sample_name=sample_name,
            source=source,
            observation_datetime=observation_datetime,
            before=before,
            after=after,
            action=action,
        )

    timestamped = _is_timestamped_name(sample_name, well_name)

    # Both importers write the timestamped name, so the well inventory
    # activity on the same event is what tells them apart.
    if event_has_inventory:
        source = WELL_INVENTORY if timestamped else UNRECOGNIZED
    elif timestamped or _is_uuid_name(sample_name):
        source = WATER_LEVEL_CSV
    else:
        source = UNRECOGNIZED

    if source == UNRECOGNIZED:
        return planned(UNRECOGNIZED, before, SKIP_UNRECOGNIZED)
    # Both sources follow the same rule; they stay apart for recognition, the
    # Location check and the report.
    if well_status in (PUBLIC, PRIVATE):
        return planned(source, well_status, CHANGE)
    return planned(source, before, SKIP_WELL_NOT_RELEASED)


def _version_statuses(session: Session, ids: list[int]) -> dict[int, set]:
    """Every release status each reading has held, from observation_version."""
    ObservationVersion = version_class(Observation)
    statuses: dict[int, set] = {}
    for batch in _batches(ids):
        for observation_id, status in session.execute(
            select(ObservationVersion.id, ObservationVersion.release_status).where(
                ObservationVersion.id.in_(batch)
            )
        ):
            statuses.setdefault(observation_id, set()).add(status)
    return statuses


def _apply_history_check(
    session: Session, readings: list[PlannedReading]
) -> list[PlannedReading]:
    to_change = [r.observation_id for r in readings if r.action == CHANGE]
    statuses = _version_statuses(session, to_change)

    checked = []
    for reading in readings:
        if reading.action != CHANGE:
            checked.append(reading)
            continue
        history = statuses.get(reading.observation_id)
        if history is None:
            checked.append(replace(reading, history_missing=True))
        # Anything but draft, including a null, means the status was not just
        # the importer's default at some point; leave the reading alone.
        elif history != {DRAFT}:
            checked.append(
                replace(reading, after=reading.before, action=SKIP_HISTORY_NON_DRAFT)
            )
        else:
            checked.append(reading)
    return checked


def _apply_location_check(
    session: Session, readings: list[PlannedReading]
) -> list[PlannedReading]:
    well_ids = sorted(
        {r.thing_id for r in readings if r.well_inventory_well and r.action == CHANGE}
    )
    location_status: dict[int, str | None] = {}
    for batch in _batches(well_ids):
        things = session.scalars(
            select(Thing)
            .where(Thing.id.in_(batch))
            .options(
                selectinload(Thing.location_associations).selectinload(
                    LocationThingAssociation.location
                )
            )
        )
        for thing in things:
            # Same property 20261001_0001 and the API use, so all three agree
            # on which Location a well is at.
            location = thing.current_location
            status = location.release_status if location is not None else None
            # A well with no current Location has nothing to agree with, which
            # is treated as a mismatch rather than a pass.
            if status != thing.release_status:
                location_status[thing.id] = status

    return [
        (
            replace(
                r,
                after=r.before,
                action=ABORT_STATUS_MISMATCH,
                location_release_status=location_status[r.thing_id],
            )
            if r.action == CHANGE and r.thing_id in location_status
            else r
        )
        for r in readings
    ]


def _plan(session: Session) -> list[PlannedReading]:
    """Read-only. Every candidate reading, with what will happen to it."""
    readings = [_classify(row) for row in _candidates(session)]
    readings = _apply_history_check(session, readings)
    return _apply_location_check(session, readings)


def _write_change_report(readings: list[PlannedReading], mode: str) -> Path:
    """Write every candidate reading and its action to a timestamped CSV.

    This is a plain filesystem write, not part of the database transaction: it
    is NOT undone by session.rollback(). That is deliberate during a dry run,
    where the report is the durable artifact you are left with after the
    database changes are discarded, but it does mean every dry run leaves its
    own file behind, hence the timestamp in the name.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H_%M_%S")
    path = REPORT_DIR / f"backfill_water_level_release_status_{stamp}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "mode",
                "observation_id",
                "well_name",
                "thing_id",
                "well_release_status",
                "well_inventory_well",
                "location_release_status",
                "sample_name",
                "source",
                "observation_datetime",
                "release_status_before",
                "release_status_after",
                "action",
                "history_missing",
            ],
        )
        writer.writeheader()
        for r in readings:
            writer.writerow(
                {
                    "mode": mode,
                    "observation_id": r.observation_id,
                    "well_name": r.well_name,
                    "thing_id": r.thing_id,
                    "well_release_status": r.well_release_status,
                    "well_inventory_well": r.well_inventory_well,
                    "location_release_status": r.location_release_status or "",
                    "sample_name": r.sample_name or "",
                    "source": r.source,
                    "observation_datetime": (
                        r.observation_datetime.isoformat()
                        if r.observation_datetime is not None
                        else ""
                    ),
                    "release_status_before": r.before,
                    "release_status_after": r.after,
                    "action": r.action,
                    "history_missing": r.history_missing,
                }
            )
    return path


def _mismatched_wells(readings: list[PlannedReading]) -> dict[int, tuple]:
    """Thing id -> (well name, well status, location status), per mismatched well.

    Keyed by id, not name, so two wells that share a name both appear.
    """
    return {
        r.thing_id: (r.well_name, r.well_release_status, r.location_release_status)
        for r in readings
        if r.action == ABORT_STATUS_MISMATCH
    }


def _describe_mismatches(mismatched: dict[int, tuple]) -> str:
    return ", ".join(
        f"{name} (thing {thing_id}: well {well}, location {location})"
        for thing_id, (name, well, location) in sorted(mismatched.items())
    )


def _log_plan(readings: list[PlannedReading], report: Path, mode: str) -> None:
    logger.info("%s %s, %d candidate readings", LOG_PREFIX, mode, len(readings))
    for r in readings:
        logger.info(
            "%s %-20s thing=%-7s obs=%-8s sample=%s %s %s: %s -> %s%s",
            LOG_PREFIX,
            r.well_name,
            r.thing_id,
            r.observation_id,
            r.sample_name,
            r.source,
            r.action,
            r.before,
            r.after,
            " (no version history)" if r.history_missing else "",
        )

    if not readings:
        logger.warning("%s no draft imported readings matched", LOG_PREFIX)
        logger.info("%s change report: %s", LOG_PREFIX, report)
        return

    by_source_action = Counter((r.source, r.action) for r in readings)
    for source in SOURCES:
        actions = {a: n for (s, a), n in by_source_action.items() if s == source}
        if actions:
            logger.info(
                "%s summary %s: %s",
                LOG_PREFIX,
                source,
                ", ".join(f"{n} {a}" for a, n in sorted(actions.items())),
            )

    changes = [r for r in readings if r.action == CHANGE]
    targets = Counter(r.after for r in changes)
    logger.info(
        "%s summary: %d readings to change, %d to public, %d to private",
        LOG_PREFIX,
        len(changes),
        targets[PUBLIC],
        targets[PRIVATE],
    )

    history_missing = sum(1 for r in changes if r.history_missing)
    if history_missing:
        logger.warning(
            "%s %d readings to change have no observation_version rows, so "
            "nothing confirms an importer left them at draft",
            LOG_PREFIX,
            history_missing,
        )

    unrecognized = by_source_action[(UNRECOGNIZED, SKIP_UNRECOGNIZED)]
    if unrecognized:
        logger.warning(
            "%s %d readings match neither importer and are left alone; "
            "check them before running",
            LOG_PREFIX,
            unrecognized,
        )

    mismatched = _mismatched_wells(readings)
    if mismatched:
        logger.error(
            "%s %d well inventory wells differ from their current Location, "
            "so run aborts: %s",
            LOG_PREFIX,
            len(mismatched),
            _describe_mismatches(mismatched),
        )
    logger.info("%s change report: %s", LOG_PREFIX, report)


def dry_run(session: Session) -> list[PlannedReading]:
    readings = _plan(session)
    _log_plan(readings, _write_change_report(readings, "dry_run"), "dry_run")
    return readings


def run(session: Session) -> None:
    readings = _plan(session)
    report = _write_change_report(readings, "run")
    _log_plan(readings, report, "run")

    mismatched = _mismatched_wells(readings)
    if mismatched:
        raise ValueError(
            "well inventory wells whose status differs from their current "
            f"Location: {_describe_mismatches(mismatched)}. Nothing was "
            f"changed; see {report}"
        )

    changes = {r.observation_id: r for r in readings if r.action == CHANGE}
    if not changes:
        return None

    # Locked and still draft: a reading someone changed after planning drops
    # out here and trips the count guard instead of being overwritten.
    observations = []
    for batch in _batches(sorted(changes)):
        observations.extend(
            session.scalars(
                select(Observation)
                .where(Observation.id.in_(batch), Observation.release_status == DRAFT)
                .with_for_update()
            )
        )

    # A partial apply would leave the report describing rows that never
    # changed, so any shift between planning and loading stops the run.
    if len(observations) != len(changes):
        raise ValueError(
            f"expected {len(changes)} draft readings to change, loaded "
            f"{len(observations)}; nothing was changed"
        )

    for observation in observations:
        observation.release_status = changes[observation.id].after

    session.flush()

    # Read back from the database, not the in-memory objects, so this checks
    # what the flush actually wrote.
    written = {}
    for batch in _batches(sorted(changes)):
        written.update(
            session.execute(
                select(Observation.id, Observation.release_status).where(
                    Observation.id.in_(batch)
                )
            ).all()
        )
    unchanged = [
        str(observation_id)
        for observation_id, change in changes.items()
        if written.get(observation_id) != change.after
    ]
    if unchanged:
        raise ValueError(f"readings not changed after flush: {', '.join(unchanged)}")

    logger.info(
        "%s changed %d readings; change report: %s",
        LOG_PREFIX,
        len(observations),
        report,
    )
    return None


MIGRATION = DataMigration(
    id="20261110_0001_backfill_imported_water_level_release_status",
    # The revision that gates ogc_waterlevels on the well's status, the view
    # this backfill is for. Pinned to it rather than the head of the day so an
    # unrelated schema change cannot hold the run back.
    alembic_revision="baba91fe5e83",
    name="Backfill release status on imported groundwater level readings",
    description=(
        "The well inventory and water level CSV importers left every "
        "groundwater level reading at draft, hiding them from the public EDR "
        "waterlevels collection. Readings from both importers take their "
        "well's public or private status; a draft well leaves them at draft. "
        "Readings whose version history shows a status "
        "other than draft are skipped, and the run aborts if a well inventory "
        "well's status differs from its current Location's (BDMS-1561)."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
