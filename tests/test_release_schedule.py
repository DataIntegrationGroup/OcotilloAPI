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
"""The scheduled release of embargoed records."""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from db.authorization_audit import RELEASE_LIFTED, AuthorizationAudit
from db.engine import session_ctx
from db.location import Location
from services.release_schedule import RELEASE_ACTOR, lift_due_embargoes

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture()
def embargoed_locations():
    """Three locations: due yesterday, due today, still held."""
    created = {}
    with session_ctx() as session:
        for label, release_at in (
            ("overdue", YESTERDAY),
            ("due", TODAY),
            ("held", TOMORROW),
        ):
            location = Location(
                point="POINT(-106.0 34.0)",
                elevation=1500.0,
                release_status="embargoed",
                release_at=release_at,
            )
            session.add(location)
            session.commit()
            session.refresh(location)
            created[label] = location.id

        yield created

        session.execute(
            delete(AuthorizationAudit).where(
                AuthorizationAudit.subject_table == Location.__tablename__,
                AuthorizationAudit.subject_id.in_(created.values()),
            )
        )
        session.execute(delete(Location).where(Location.id.in_(created.values())))
        session.commit()


def _status(session, location_id):
    location = session.get(Location, location_id)
    return location.release_status, location.release_at


def test_a_record_is_released_on_its_date(embargoed_locations):
    with session_ctx() as session:
        lift_due_embargoes(session)
        assert _status(session, embargoed_locations["due"]) == ("public", None)


def test_a_record_whose_date_passed_unnoticed_is_still_released(embargoed_locations):
    """A day the job did not run does not strand the record."""
    with session_ctx() as session:
        lift_due_embargoes(session)
        assert _status(session, embargoed_locations["overdue"]) == ("public", None)


def test_a_record_still_under_embargo_is_left_alone(embargoed_locations):
    with session_ctx() as session:
        lift_due_embargoes(session)
        assert _status(session, embargoed_locations["held"]) == (
            "embargoed",
            TOMORROW,
        )


def test_the_release_date_is_cleared_on_release(embargoed_locations):
    """A public row carrying a release_at would advertise a schedule it has
    already kept, and would fail validate_release if it were re-checked."""
    with session_ctx() as session:
        lift_due_embargoes(session)
        _, release_at = _status(session, embargoed_locations["due"])
        assert release_at is None


def test_a_preview_writes_nothing(embargoed_locations):
    with session_ctx() as session:
        plan = lift_due_embargoes(session, apply=False)
        assert len(plan.lifted) == 2
        assert _status(session, embargoed_locations["due"]) == ("embargoed", TODAY)
        assert _status(session, embargoed_locations["overdue"]) == (
            "embargoed",
            YESTERDAY,
        )


def test_running_twice_releases_nothing_the_second_time(embargoed_locations):
    with session_ctx() as session:
        first = lift_due_embargoes(session)
        second = lift_due_embargoes(session)
        assert len(first.lifted) == 2
        assert second.lifted == []


def test_every_release_lands_in_the_authorization_log(embargoed_locations):
    """The question after an incident is who published this, and when."""
    with session_ctx() as session:
        lift_due_embargoes(session)
        rows = (
            session.execute(
                select(AuthorizationAudit).where(
                    AuthorizationAudit.subject_table == Location.__tablename__,
                    AuthorizationAudit.subject_id.in_(embargoed_locations.values()),
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 2
    assert {row.event_type for row in rows} == {RELEASE_LIFTED}
    assert {row.actor for row in rows} == {RELEASE_ACTOR}

    by_subject = {row.subject_id: row.detail for row in rows}
    # The date the embargo was set for is recorded next to the date it was
    # actually lifted, so "was this released early" stays answerable.
    assert by_subject[embargoed_locations["due"]]["release_at"] == TODAY.isoformat()
    assert (
        by_subject[embargoed_locations["overdue"]]["release_at"]
        == YESTERDAY.isoformat()
    )
    assert by_subject[embargoed_locations["due"]]["released_on"] == TODAY.isoformat()


def test_an_earlier_run_date_releases_less(embargoed_locations):
    """on_date is a parameter so the job can be reasoned about, and so a
    backfill can be replayed as of a past date."""
    with session_ctx() as session:
        plan = lift_due_embargoes(session, on_date=YESTERDAY, apply=False)
        assert len(plan.lifted) == 1
        assert plan.lifted[0][1] == embargoed_locations["overdue"]


def test_a_record_at_another_level_is_left_where_it_is():
    """Only 'embargoed' is scheduled. The job walks past everything else --
    a private record is not published because the job happened to look at it.

    It carries no release_at: the CHECK constraint below makes that pairing
    unwritable, which is a stronger guarantee than this test could assert.
    """
    with session_ctx() as session:
        location = Location(
            point="POINT(-106.1 34.1)",
            elevation=1500.0,
            release_status="private",
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        location_id = location.id

        try:
            lift_due_embargoes(session)
            assert _status(session, location_id) == ("private", None)
        finally:
            session.execute(delete(Location).where(Location.id == location_id))
            session.commit()


# ------ the table refuses what the schema layer cannot see ----------


def test_the_table_rejects_an_embargo_with_no_date():
    """A PATCH body carrying only release_status is a fragment, so the pair is
    guarded by a CHECK constraint rather than by pydantic. This is that
    constraint, reached the way the CLI and the transfers reach it."""
    with session_ctx() as session:
        session.add(
            Location(
                point="POINT(-106.2 34.2)",
                elevation=1500.0,
                release_status="embargoed",
                release_at=None,
            )
        )
        # pg8000 maps a CHECK violation (SQLSTATE 23514) to ProgrammingError
        # rather than IntegrityError, so match on the parent and the name.
        with pytest.raises(DBAPIError, match="location_embargo_needs_date"):
            session.commit()
        session.rollback()


def test_the_table_rejects_a_release_date_without_an_embargo():
    with session_ctx() as session:
        session.add(
            Location(
                point="POINT(-106.3 34.3)",
                elevation=1500.0,
                release_status="draft",
                release_at=TOMORROW,
            )
        )
        with pytest.raises(DBAPIError, match="location_embargo_needs_date"):
            session.commit()
        session.rollback()


def test_the_released_row_satisfies_the_constraint(embargoed_locations):
    """The job clears release_at as it publishes; if it did not, its own
    UPDATE would violate the constraint it just satisfied."""
    with session_ctx() as session:
        lift_due_embargoes(session)
        assert _status(session, embargoed_locations["due"]) == ("public", None)
