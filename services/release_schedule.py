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
services/release_schedule.py

Lifts embargoes whose date has arrived: `release_status = 'embargoed'` becomes
`'public'` once `release_at` is reached.

**Why a job rather than a predicate in the views.** Seven of the public OGC
collections are materialized views refreshed by one pg_cron job at 09:00 UTC
(migration ``b6c7d8e9f0a1``). ``current_date`` inside a matview is frozen at
refresh time, so a date predicate in the view SQL would buy nothing on more
than half the public surface while costing a recreation of every relation.
The refresh already sets the granularity; this job runs before it and leaves
``release_status`` as the only thing the views test.

**Fail closed.** If this job does not run, embargoed records stay embargoed.
The failure mode is data staying private a day longer than promised, which is
the direction that does not require an apology.

**One direction.** Nothing here makes a record less visible. Withdrawing
something already published is an immediate `release_status` change made by a
person, for the reason ``domain/access.py`` never backdates a revocation.

Every flip lands an ``authorization_audit`` row in the same transaction, and
records the date the embargo was set for, so the log answers "was this
released early" and not only "was this released".
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from db.authorization_audit import RELEASE_LIFTED, AuthorizationAudit
from db.field import FieldActivity, FieldEvent
from db.location import Location
from db.observation import Observation
from db.sample import Sample
from db.thing import Thing
from domain.release import STATUS_EMBARGOED, STATUS_PUBLIC, due_for_release

# Recorded as the actor. Not a person: nobody decided anything on the day the
# embargo lifted, which is the point of scheduling it.
RELEASE_ACTOR = "system:release-schedule"

# The models a scheduled release may touch, named one by one.
#
# Every `ReleaseMixin` model carries `release_at`, so this could iterate the
# mapper registry instead. It does not, for the reason `domain/access.py` has
# no wildcard data type: a model added next year should not silently join the
# set of things a nightly job rewrites. Adding one here is a deliberate line
# in a diff.
#
# These six are the water-level chain the public OGC views actually filter on
# -- thing, location, and the field-data path down to the observation -- so an
# embargo on any of them changes what `/ogcapi` publishes. Chemistry is
# absent: those collections read the legacy `NMA_*` tables, which carry no
# release columns at all. See docs/data-embargo.md.
RELEASABLE_MODELS = (
    Thing,
    Location,
    FieldEvent,
    FieldActivity,
    Sample,
    Observation,
)


@dataclass
class ReleasePlan:
    """What lifting would do, or did."""

    lifted: list = field(default_factory=list)

    def describe(self, entry) -> str:
        table, row_id, release_at = entry
        return f"{table}:{row_id} embargoed until {release_at.isoformat()}"

    def by_table(self) -> dict:
        counts: dict = {}
        for table, _, _ in self.lifted:
            counts[table] = counts.get(table, 0) + 1
        return counts


def _due_rows(session, model, on_date: date) -> list:
    """Embargoed rows of one model whose date has arrived.

    The date test is narrowed in SQL so the job does not load every embargoed
    row in the database, and then applied again by ``due_for_release`` on each
    candidate. The rule lives in the domain function; the WHERE clause is an
    optimisation that is allowed to be looser than it, never tighter.
    """
    rows = session.execute(
        select(model).where(
            model.release_status == STATUS_EMBARGOED,
            model.release_at.is_not(None),
            model.release_at <= on_date,
        )
    ).scalars()
    return [
        row
        for row in rows
        if due_for_release(row.release_status, row.release_at, on_date)
    ]


def lift_due_embargoes(
    session, on_date: date = None, apply: bool = True
) -> ReleasePlan:
    """Publish every record whose embargo has run out. Safe to run repeatedly.

    With ``apply=False`` nothing is written and the plan describes what would
    be. Release is security state, so the CLI previews by default.

    Idempotent by construction: a lifted row is no longer ``embargoed``, so the
    next run does not see it.
    """
    on_date = on_date or date.today()
    plan = ReleasePlan()

    for model in RELEASABLE_MODELS:
        table = model.__tablename__
        for row in _due_rows(session, model, on_date):
            plan.lifted.append((table, row.id, row.release_at))
            if not apply:
                continue

            embargoed_until = row.release_at
            row.release_status = STATUS_PUBLIC
            # Cleared so the row stops advertising a schedule it has already
            # kept, and so `validate_release` still holds for it afterwards:
            # a release_at on a public row schedules nothing.
            row.release_at = None
            session.add(
                AuthorizationAudit(
                    event_type=RELEASE_LIFTED,
                    actor=RELEASE_ACTOR,
                    subject_table=table,
                    subject_id=row.id,
                    detail={
                        "release_at": embargoed_until.isoformat(),
                        "released_on": on_date.isoformat(),
                        "from_status": STATUS_EMBARGOED,
                        "to_status": STATUS_PUBLIC,
                    },
                )
            )

    if apply and plan.lifted:
        session.commit()

    return plan


# ============= EOF =============================================
