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
Embargo rules, as plain functions over plain values.

An embargo is a record held back from public release until a date that was
decided in advance: `release_status = 'embargoed'` plus a `release_at`. When
the date arrives, `services/release_schedule.py` flips the level to `public`
and the record appears in the OGC views on their next refresh.

Three invariants this module exists to keep:

* **Intent is not enforcement.** `release_status` is the only thing the views
  filter on. `release_at` says when that level is due to change and is read by
  the release job alone. This module therefore publishes no "is this visible"
  predicate: one that compared dates would disagree with the views for up to a
  day and would eventually be used as a read-path filter, which is the
  distributed filtering ADR5 exists to prevent (see migration `baba91fe5e83`).

* **An embargo only ever widens visibility.** The scheduled path turns
  `embargoed` into `public` and does nothing else. Making a record *less*
  visible is an immediate change to `release_status`, never a scheduled one,
  for the same reason a revocation in `domain/access.py` is never backdated:
  a promise to hide something later is not a promise anybody should rely on.

* **An embargo names its date.** `embargoed` without a `release_at` would be
  a hold nothing ever lifts, and a `release_at` on any other level would be a
  date nothing ever reads. Both are rejected before the row is written. An
  indefinite hold is `private`, which is honest about never lifting itself.
"""

from datetime import date

# The level a record sits at while it is being withheld, and the one the
# scheduled release moves it to. Spelled as the lexicon spells them;
# tests/test_domain_release.py pins these against core/lexicon.json so a
# rename there cannot silently strand the release job.
STATUS_EMBARGOED = "embargoed"
STATUS_PUBLIC = "public"
# The level for a hold that nothing lifts. Named here only so the error
# message can point at it.
STATUS_PRIVATE = "private"


class ReleaseRuleError(ValueError):
    """Base for embargo rule violations. A ValueError, per ADR4."""


class MissingReleaseDate(ReleaseRuleError):
    pass


class UnscheduledReleaseDate(ReleaseRuleError):
    pass


def validate_release(release_status: str | None, release_at: date | None) -> None:
    """Reject an embargo that could not be lifted honestly.

    Raised before a row is written, so the invariant holds in the table
    rather than in the reader.
    """
    if release_status == STATUS_EMBARGOED and release_at is None:
        raise MissingReleaseDate(
            "An embargoed record names the date it is released. For a hold "
            f"with no end, use '{STATUS_PRIVATE}' instead."
        )
    if release_at is not None and release_status != STATUS_EMBARGOED:
        raise UnscheduledReleaseDate(
            f"release_at is only read for '{STATUS_EMBARGOED}' records, so "
            f"setting it on a '{release_status}' record schedules nothing."
        )


def due_for_release(
    release_status: str | None,
    release_at: date | None,
    on_date: date,
) -> bool:
    """Whether this record's embargo has run out by ``on_date``.

    The only date comparison in the embargo feature, and it belongs to the
    release job. A record is due on its ``release_at`` itself, not the day
    after: the date is when the record becomes public, not the last day it is
    held.
    """
    if release_status != STATUS_EMBARGOED:
        return False
    if release_at is None:
        # Unreachable through validate_release, but a row written before this
        # module existed, or by hand, must not crash the nightly job.
        return False
    return on_date >= release_at


# ============= EOF =============================================
