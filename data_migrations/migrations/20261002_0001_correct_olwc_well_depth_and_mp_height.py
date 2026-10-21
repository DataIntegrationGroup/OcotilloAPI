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
Apply the corrections decided from comparing the OLWC 2025 water level
monitoring spreadsheet against staging.

Three things differed, and each has a different fix:

* Well depth. Six wells have a depth in the spreadsheet and none in the
  database. The spreadsheet value is copied onto ``Thing.well_depth``. No
  ``data_provenance`` row is written; the source is deliberately left blank.
* Observed MP height. ``OG-0042`` and ``OG-0066`` were stored with the wrong
  sign (the measuring point is recessed, so the height is negative), and
  ``OG-0072`` has 0.4 where the legacy database has -0.4. The two older
  readings of each are corrected. Their latest reading already agrees.
* History MP height. ``Thing.measuring_point_height`` reads the newest
  ``measuring_point_history`` row with a height, and these wells only had a
  null placeholder row, so the API reported no MP height even where the
  observations carried one. Each placeholder is filled in to match the
  corrected observations.

The placeholder rows start on 2026-02-27, the day the Things were created, and
that date is kept: the decision was to use the creation date as the start date.
Two wells changed MP height between readings, so one placeholder is not enough
for them. ``OG-0016`` (0.9 then 0.4) and ``OG-0072`` (-0.4 then 0) become a
closed earlier row dated from the first reading plus a current row dated from the
first reading that shows the new height. The placeholder is reused as the current
row, because ``Thing.measuring_point_height`` ignores ``end_date`` and picks the
newest ``start_date``, so the current row has to carry the latest one.

Wells are identified by ``Thing.name`` among water wells, and readings by well
plus UTC date. Every precondition is checked before anything is written, and all
problems are reported together: the well exists exactly once, the depth is still
empty, each reading still holds the expected old value, and each well has just
the one open, null-height placeholder. A value already at its target is skipped,
so a partly applied run can be finished. Any other value raises, so a database
that differs from staging stops for a person to look at instead of being
overwritten.

``Thing`` and ``Observation`` are mutated by attribute assignment rather than a
bulk Core ``update()``. Both are SQLAlchemy-Continuum versioned, and Continuum
only writes ``thing_version`` and ``observation_version`` rows from the Session's
unit of work. ``MeasuringPointHistory`` is not versioned, so nothing records its
old values except the change report this migration writes. Keep that file.

There is no reverse migration. To undo, write a second narrow migration that
restores the values in the change report, cross-checked against
``thing_version`` and ``observation_version``. Do not use Continuum's
``.revert()``: it restores every versioned column on the row, not just these.

Review the dry run before applying:

    oco data-migrations run 20261002_0001_correct_olwc_well_depth_and_mp_height --dry-run
    oco data-migrations run 20261002_0001_correct_olwc_well_depth_and_mp_height
    oco data-migrations status
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.field import FieldActivity, FieldEvent
from db.measuring_point_history import MeasuringPointHistory
from db.observation import Observation
from db.sample import Sample
from db.thing import Thing
from transfers.logger import logger

WELL_THING_TYPE = "water well"
REASON = "Backfilled from the OLWC 2025 water level monitoring data."

REPORT_DIR = Path("reports")

# Kept local rather than imported: a migration must reproduce the decisions it
# ran with, and cannot track a moving import. Every value below comes from the
# reviewed OLWC comparison workbook.

# Feet. These wells have no depth in the database today.
WELL_DEPTHS: dict[str, float] = {
    "OG-0079": 437.0,
    "OG-0086": 430.0,
    "OG-0087": 376.0,
    "OG-0002": 517.0,
    "OG-0010": 463.0,
    "OG-0016": 495.0,
}

# (well, reading date, old MP height, new MP height). OG-0072 goes to -0.4, the
# legacy database value, not the 0 the spreadsheet shows.
OBSERVATION_MP_FIXES: list[tuple[str, date, float, float]] = [
    ("OG-0042", date(2023, 1, 24), 0.1, -0.1),
    ("OG-0042", date(2024, 12, 18), 0.1, -0.1),
    ("OG-0066", date(2023, 1, 24), 0.3, -0.3),
    ("OG-0066", date(2024, 12, 18), 0.3, -0.3),
    ("OG-0072", date(2023, 1, 25), 0.4, -0.4),
    ("OG-0072", date(2024, 12, 19), 0.4, -0.4),
]

# One height for the well's whole history. The placeholder row keeps its start
# date, which is the Thing's creation date.
HISTORY_SET: dict[str, float] = {
    "OG-0079": 4.0,
    "OG-0081": 3.55,
    "OG-0082": 3.65,
    "OG-0084": 3.9,
    "OG-0086": 2.8,
    "OG-0087": 2.7,
    "OG-0002": 0.17,
    "OG-0010": 0.14,
    "OG-0027": 1.15,
    "OG-0056": 2.16,
    "OG-0061": 0.35,
    "CP-0019": 1.0,
    "OG-0042": -0.1,
    "OG-0066": -0.3,
}

# (height, start_date, end_date) per row, earliest first. The last row is the
# current one and must stay open. The change happened before the Things were
# created, so these dates come from the readings, not the creation date: the
# earlier row starts at the first reading, and the current row starts at the
# first reading that shows the new height.
HISTORY_SPLIT: dict[str, list[tuple[float, date, date | None]]] = {
    "OG-0016": [
        (0.9, date(2023, 1, 23), date(2024, 12, 18)),
        (0.4, date(2024, 12, 18), None),
    ],
    "OG-0072": [
        (-0.4, date(2023, 1, 25), date(2025, 12, 18)),
        (0.0, date(2025, 12, 18), None),
    ],
}


@dataclass
class PlannedChange:
    well_name: str
    table: str
    row_id: int | None  # None until an inserted row is flushed
    detail: str
    field: str
    before: object
    after: object
    apply: Callable[[], None]


@dataclass
class Plan:
    changes: list[PlannedChange]
    skipped: list[str]


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _same_float(a, b) -> bool:
    return a is not None and abs(a - b) < 1e-9


def _setter(obj, attr, value) -> Callable[[], None]:
    return lambda: setattr(obj, attr, value)


def _inserter(session, row) -> Callable[[], None]:
    # The row is built at planning time but only added on apply, so a dry run
    # never puts it in the session.
    return lambda: session.add(row)


def _find_things(session: Session, names: set[str], problems: list[str]) -> dict:
    things: dict[str, Thing] = {}
    for name in sorted(names):
        found = session.scalars(
            select(Thing).where(Thing.name == name, Thing.thing_type == WELL_THING_TYPE)
        ).all()
        if len(found) != 1:
            problems.append(f"{name}: expected 1 water well, found {len(found)}")
            continue
        things[name] = found[0]
    return things


def _plan_well_depths(things, changes, skipped, problems) -> None:
    for name, depth in WELL_DEPTHS.items():
        thing = things.get(name)
        if thing is None:
            continue
        if _same_float(thing.well_depth, depth):
            skipped.append(f"{name}: well_depth already {depth}")
        elif thing.well_depth is not None:
            problems.append(
                f"{name}: well_depth is {thing.well_depth}, expected empty or {depth}"
            )
        else:
            changes.append(
                PlannedChange(
                    name,
                    "thing",
                    thing.id,
                    "",
                    "well_depth",
                    None,
                    depth,
                    _setter(thing, "well_depth", depth),
                )
            )


def _readings_on(session: Session, thing: Thing, day: date) -> list[Observation]:
    """Water level readings (the only observations carrying an MP height) on a UTC day."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return list(
        session.scalars(
            select(Observation)
            .join(Sample, Observation.sample_id == Sample.id)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
            .where(
                FieldEvent.thing_id == thing.id,
                Observation.measuring_point_height.isnot(None),
                Observation.observation_datetime >= start,
                Observation.observation_datetime < start + timedelta(days=1),
            )
        ).all()
    )


def _plan_observation_fixes(session, things, changes, skipped, problems) -> None:
    for name, day, old, new in OBSERVATION_MP_FIXES:
        thing = things.get(name)
        if thing is None:
            continue
        readings = _readings_on(session, thing, day)
        if len(readings) != 1:
            problems.append(
                f"{name}: expected 1 reading with an MP height on {day}, "
                f"found {len(readings)}"
            )
            continue
        reading = readings[0]
        if _same_float(reading.measuring_point_height, new):
            skipped.append(f"{name}: {day} reading MP already {new}")
        elif not _same_float(reading.measuring_point_height, old):
            problems.append(
                f"{name}: {day} reading MP is {reading.measuring_point_height}, "
                f"expected {old}"
            )
        else:
            changes.append(
                PlannedChange(
                    name,
                    "observation",
                    reading.id,
                    f"reading {day}",
                    "measuring_point_height",
                    old,
                    new,
                    _setter(reading, "measuring_point_height", new),
                )
            )


def _history_rows(session: Session, thing: Thing) -> list[MeasuringPointHistory]:
    return list(
        session.scalars(
            select(MeasuringPointHistory)
            .where(MeasuringPointHistory.thing_id == thing.id)
            .order_by(MeasuringPointHistory.start_date, MeasuringPointHistory.id)
        ).all()
    )


def _is_placeholder(row: MeasuringPointHistory) -> bool:
    return row.measuring_point_height is None and row.end_date is None


def _describe(rows: list[MeasuringPointHistory]) -> str:
    return "; ".join(
        f"{r.measuring_point_height} {r.start_date} to {r.end_date}" for r in rows
    )


def _plan_history_set(session, things, changes, skipped, problems) -> None:
    for name, height in HISTORY_SET.items():
        thing = things.get(name)
        if thing is None:
            continue
        rows = _history_rows(session, thing)
        target = _dec(height)
        if len(rows) == 1 and _is_placeholder(rows[0]):
            row = rows[0]
            changes.append(
                PlannedChange(
                    name,
                    "measuring_point_history",
                    row.id,
                    f"start {row.start_date}",
                    "measuring_point_height",
                    None,
                    height,
                    _setter(row, "measuring_point_height", target),
                )
            )
            if row.reason is None:
                changes.append(
                    PlannedChange(
                        name,
                        "measuring_point_history",
                        row.id,
                        f"start {row.start_date}",
                        "reason",
                        None,
                        REASON,
                        _setter(row, "reason", REASON),
                    )
                )
        elif (
            len(rows) == 1
            and rows[0].end_date is None
            and rows[0].measuring_point_height == target
        ):
            skipped.append(f"{name}: history MP already {height}")
        else:
            problems.append(
                f"{name}: expected one open null-height history row, "
                f"found {len(rows)}: {_describe(rows)}"
            )


def _plan_history_split(session, things, changes, skipped, problems) -> None:
    for name, periods in HISTORY_SPLIT.items():
        thing = things.get(name)
        if thing is None:
            continue
        rows = _history_rows(session, thing)
        already = len(rows) == len(periods) and all(
            row.measuring_point_height == _dec(height)
            and row.start_date == start
            and row.end_date == end
            for row, (height, start, end) in zip(rows, periods)
        )
        if already:
            skipped.append(f"{name}: history MP already split")
            continue
        if not (len(rows) == 1 and _is_placeholder(rows[0])):
            problems.append(
                f"{name}: expected one open null-height history row, "
                f"found {len(rows)}: {_describe(rows)}"
            )
            continue

        placeholder = rows[0]
        *earlier, current = periods
        for height, start, end in earlier:
            changes.append(
                PlannedChange(
                    name,
                    "measuring_point_history",
                    None,
                    f"insert {start} to {end}",
                    "measuring_point_height",
                    None,
                    height,
                    _inserter(
                        session,
                        MeasuringPointHistory(
                            thing_id=thing.id,
                            measuring_point_height=_dec(height),
                            start_date=start,
                            end_date=end,
                            reason=REASON,
                            # The model default is draft; the placeholder
                            # carries the status the well really has.
                            release_status=placeholder.release_status,
                        ),
                    ),
                )
            )
        height, start, _ = current
        detail = f"start {placeholder.start_date}"
        changes.append(
            PlannedChange(
                name,
                "measuring_point_history",
                placeholder.id,
                detail,
                "measuring_point_height",
                None,
                height,
                _setter(placeholder, "measuring_point_height", _dec(height)),
            )
        )
        changes.append(
            PlannedChange(
                name,
                "measuring_point_history",
                placeholder.id,
                detail,
                "start_date",
                placeholder.start_date,
                start,
                _setter(placeholder, "start_date", start),
            )
        )
        if placeholder.reason is None:
            changes.append(
                PlannedChange(
                    name,
                    "measuring_point_history",
                    placeholder.id,
                    detail,
                    "reason",
                    None,
                    REASON,
                    _setter(placeholder, "reason", REASON),
                )
            )


def _plan(session: Session) -> Plan:
    """Read-only. Every change to make, or a ValueError listing every problem."""
    names = (
        set(WELL_DEPTHS)
        | {fix[0] for fix in OBSERVATION_MP_FIXES}
        | set(HISTORY_SET)
        | set(HISTORY_SPLIT)
    )
    changes: list[PlannedChange] = []
    skipped: list[str] = []
    problems: list[str] = []

    things = _find_things(session, names, problems)
    _plan_well_depths(things, changes, skipped, problems)
    _plan_observation_fixes(session, things, changes, skipped, problems)
    _plan_history_set(session, things, changes, skipped, problems)
    _plan_history_split(session, things, changes, skipped, problems)

    if problems:
        raise ValueError(
            "OLWC corrections cannot be applied; nothing was written:\n  "
            + "\n  ".join(problems)
        )
    return Plan(changes=changes, skipped=skipped)


def _write_change_report(changes: list[PlannedChange]) -> Path:
    """Write what changed to a timestamped CSV.

    This is a plain filesystem write, not part of the database transaction: it
    is NOT undone by session.rollback(). That is deliberate during a dry run,
    where the report is the durable artifact you are left with after the
    database changes are discarded, but it does mean every dry run leaves its
    own file behind, hence the timestamp in the name. It is also the only record
    of the old measuring_point_history values, which are not versioned.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H_%M_%S")
    path = REPORT_DIR / f"correct_olwc_well_depth_and_mp_height_{stamp}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "well_name",
                "table",
                "row_id",
                "detail",
                "field",
                "before",
                "after",
            ],
        )
        writer.writeheader()
        for change in changes:
            writer.writerow(
                {
                    "well_name": change.well_name,
                    "table": change.table,
                    "row_id": change.row_id,
                    "detail": change.detail,
                    "field": change.field,
                    "before": change.before,
                    "after": change.after,
                }
            )
    return path


def _log_plan(plan: Plan, report: Path) -> None:
    for change in plan.changes:
        logger.info(
            "  %-8s %-24s id=%-7s %-22s %s: %s -> %s",
            change.well_name,
            change.table,
            change.row_id if change.row_id is not None else "new",
            change.detail,
            change.field,
            change.before,
            change.after,
        )
    for note in plan.skipped:
        logger.info("  skipped: %s", note)
    if not plan.changes:
        logger.warning("OLWC corrections - nothing to change")
    logger.info(
        "OLWC corrections - %d changes, %d already applied; change report: %s",
        len(plan.changes),
        len(plan.skipped),
        report,
    )


def dry_run(session: Session) -> list[PlannedChange]:
    plan = _plan(session)
    _log_plan(plan, _write_change_report(plan.changes))
    return plan.changes


def run(session: Session) -> None:
    plan = _plan(session)
    report = _write_change_report(plan.changes)
    _log_plan(plan, report)

    if not plan.changes:
        return None

    for change in plan.changes:
        change.apply()
    session.flush()

    # Planning again must find nothing left to do. That catches a change that
    # silently did not take, which would otherwise leave the report describing
    # rows that never changed.
    remaining = _plan(session).changes
    if remaining:
        raise ValueError(
            "OLWC corrections not fully applied after flush: "
            + ", ".join(f"{c.well_name} {c.table}.{c.field}" for c in remaining)
        )

    logger.info(
        "OLWC corrections - applied %d changes; change report: %s",
        len(plan.changes),
        report,
    )
    return None


MIGRATION = DataMigration(
    id="20261002_0001_correct_olwc_well_depth_and_mp_height",
    alembic_revision="a3b4c5d6e7f8",
    name="Apply OLWC 2025 well depth and MP height corrections",
    description=(
        "Sets well depth on six OLWC wells, fixes the sign and value of older "
        "observed MP heights on OG-0042, OG-0066 and OG-0072, and fills the "
        "null measuring point history rows so Thing.measuring_point_height "
        "matches the observations. OG-0016 and OG-0072 get two dated history "
        "rows. Decided from the OLWC 2025 spreadsheet comparison."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)


# ============= EOF =============================================
