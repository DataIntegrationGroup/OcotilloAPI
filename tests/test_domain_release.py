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
"""Embargo rules, exercised without a database."""

from datetime import date, timedelta

import pytest

from domain.release import (
    STATUS_EMBARGOED,
    STATUS_PRIVATE,
    STATUS_PUBLIC,
    MissingReleaseDate,
    UnscheduledReleaseDate,
    due_for_release,
    validate_release,
)

TODAY = date(2026, 9, 1)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


# ------ when an embargo runs out ----------


def test_an_embargo_lifts_on_its_release_date():
    """release_at is the day the record becomes public, not the last day it
    is held. Off by one here publishes a day late, every time."""
    assert due_for_release(STATUS_EMBARGOED, TODAY, TODAY) is True


def test_an_embargo_is_still_holding_the_day_before():
    assert due_for_release(STATUS_EMBARGOED, TOMORROW, TODAY) is False


def test_a_missed_run_still_releases_afterwards():
    """The job does not have to run on the day. A date that passed while
    nothing ran is still due the next time it does."""
    assert due_for_release(STATUS_EMBARGOED, YESTERDAY, TODAY) is True


def test_expiry_is_checked_at_use_not_swept():
    """The same row answers differently on different days, with no job run."""
    assert due_for_release(STATUS_EMBARGOED, TODAY, YESTERDAY) is False
    assert due_for_release(STATUS_EMBARGOED, TODAY, TODAY) is True


# ------ what the release job refuses to touch ----------


@pytest.mark.parametrize(
    "status", [STATUS_PUBLIC, STATUS_PRIVATE, "draft", "archived", None]
)
def test_only_embargoed_records_are_released(status):
    """A past date on any other level schedules nothing. Publishing a draft
    because it happens to carry a date would be the job inventing a decision
    nobody made."""
    assert due_for_release(status, YESTERDAY, TODAY) is False


def test_an_embargo_without_a_date_is_never_due():
    """validate_release makes this unwritable, but a row predating this
    feature, or written by hand, must not crash the nightly job."""
    assert due_for_release(STATUS_EMBARGOED, None, TODAY) is False


# ------ validation, before a row is written ----------


def test_an_embargo_names_its_release_date():
    with pytest.raises(MissingReleaseDate):
        validate_release(STATUS_EMBARGOED, None)


def test_a_release_date_on_another_level_is_rejected():
    """It would schedule nothing, and read as a promise that something was."""
    with pytest.raises(UnscheduledReleaseDate):
        validate_release("draft", TOMORROW)


def test_a_public_record_carries_no_release_date():
    with pytest.raises(UnscheduledReleaseDate):
        validate_release(STATUS_PUBLIC, TOMORROW)


def test_an_embargo_with_a_date_is_valid():
    assert validate_release(STATUS_EMBARGOED, TOMORROW) is None


def test_a_record_with_neither_is_valid():
    assert validate_release("draft", None) is None


def test_a_release_date_in_the_past_is_accepted():
    """Backfilling an embargo that already expired is a legitimate thing to
    do; the next run publishes it. Rejecting it would push the caller into
    setting a fake future date."""
    assert validate_release(STATUS_EMBARGOED, YESTERDAY) is None


# ------ the domain constants and the lexicon must agree ----------


def test_the_release_levels_exist_in_the_lexicon():
    """domain/release.py cannot import the lexicon without taking a database
    dependency, so its constants are hand-copied -- the same drift that cost
    domain/access.py every API-key grant. A rename in core/lexicon.json that
    stranded the release job would otherwise be silent: nothing would ever be
    due, and nothing would raise."""
    from core.enums import ReleaseStatus

    levels = {member.value for member in ReleaseStatus}
    assert STATUS_EMBARGOED in levels
    assert STATUS_PUBLIC in levels
    assert STATUS_PRIVATE in levels
