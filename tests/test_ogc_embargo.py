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
"""An embargoed record must not reach the public OGC relations.

The whole feature is one claim -- "this measurement is not published until
that date" -- and this is where it is checked against the relations a
consumer actually reads, rather than against the rule in isolation.

The four relations here are the public ones that read the observation chain
(migration b4c5d6e7f8a9). The chemistry collections are absent because they
read the legacy NMA_* tables, which carry no release columns at all; see
docs/data-embargo.md.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, text

from db.engine import session_ctx
from db.field import FieldActivity, FieldEvent
from db.location import Location, LocationThingAssociation
from db.observation import Observation
from db.sample import Sample
from db.thing import Thing
from services.release_schedule import lift_due_embargoes
from tests import get_parameter_id

POINT_ID = "EMBARGO-TEST-1"
TOMORROW = date.today() + timedelta(days=1)

# Every public relation that reads the observation chain, with the matviews
# flagged: those answer from their last refresh, so a test that changes data
# has to refresh them the way the nightly pg_cron job does.
WATER_LEVEL_RELATIONS = (
    ("ogc_water_well_summary", True),
    ("ogc_water_elevation_wells", True),
    ("ogc_depth_to_water_trend_wells", True),
    ("ogc_latest_depth_to_water_wells", True),
)


def _refresh(session):
    for relation, materialized in WATER_LEVEL_RELATIONS:
        if materialized:
            session.execute(text(f"REFRESH MATERIALIZED VIEW {relation}"))
    session.commit()


def _relations_naming(session, thing_id) -> set:
    """Which of the public relations currently publish this well."""
    present = set()
    for relation, _materialized in WATER_LEVEL_RELATIONS:
        found = session.execute(
            text(f"SELECT 1 FROM {relation} WHERE id = :id LIMIT 1"),
            {"id": thing_id},
        ).scalar()
        if found:
            present.add(relation)
    return present


@pytest.fixture()
def well_with_one_water_level():
    """A public well whose only measurement is public, and its ids."""
    with session_ctx() as session:
        location = Location(
            point="POINT(-106.5 34.5)",
            elevation=1600.0,
            release_status="public",
        )
        session.add(location)
        session.flush()

        thing = Thing(
            name=POINT_ID,
            thing_type="water well",
            release_status="public",
            well_depth=100.0,
        )
        session.add(thing)
        session.flush()

        session.add(
            LocationThingAssociation(
                location_id=location.id,
                thing_id=thing.id,
                effective_start="2025-02-01T00:00:00Z",
            )
        )

        event = FieldEvent(
            thing_id=thing.id,
            event_date="2024-03-15T19:00:00Z",
            release_status="public",
        )
        session.add(event)
        session.flush()

        activity = FieldActivity(
            field_event_id=event.id,
            activity_type="groundwater level",
            release_status="public",
        )
        session.add(activity)
        session.flush()

        sample = Sample(
            field_activity_id=activity.id,
            sample_date="2024-03-15T19:00:00Z",
            sample_name=f"{POINT_ID}-wl-1",
            sample_matrix="water",
            sample_method="Steel-tape measurement",
            qc_type="Normal",
            release_status="public",
        )
        session.add(sample)
        session.flush()

        observation = Observation(
            sample_id=sample.id,
            parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
            observation_datetime="2024-03-15T19:00:00Z",
            value=50.0,
            unit="ft",
            measuring_point_height=2.5,
            release_status="public",
        )
        session.add(observation)
        session.commit()

        ids = {
            "thing": thing.id,
            "location": location.id,
            "observation": observation.id,
            "sample": sample.id,
            "activity": activity.id,
            "event": event.id,
        }
        _refresh(session)

        yield ids

        session.execute(delete(Thing).where(Thing.id == ids["thing"]))
        session.execute(delete(Location).where(Location.id == ids["location"]))
        session.commit()
        _refresh(session)


def test_a_public_measurement_reaches_every_water_level_relation(
    well_with_one_water_level,
):
    """The control. Without this, a test asserting absence proves nothing --
    the well could be missing for any of a dozen unrelated reasons."""
    with session_ctx() as session:
        present = _relations_naming(session, well_with_one_water_level["thing"])
    assert present == {relation for relation, _ in WATER_LEVEL_RELATIONS}


@pytest.mark.parametrize(
    "level, model",
    [
        ("observation", Observation),
        ("sample", Sample),
        ("activity", FieldActivity),
        ("event", FieldEvent),
    ],
)
def test_an_embargo_anywhere_in_the_chain_withholds_the_measurement(
    well_with_one_water_level, level, model
):
    """Embargoing any link hides the measurement. A consumer cannot reach an
    embargoed reading by way of a public parent."""
    with session_ctx() as session:
        row = session.get(model, well_with_one_water_level[level])
        row.release_status = "embargoed"
        row.release_at = TOMORROW
        session.commit()
        _refresh(session)

        assert _relations_naming(session, well_with_one_water_level["thing"]) == set()


def test_an_embargoed_well_is_absent_from_every_relation(well_with_one_water_level):
    """Whole-site embargo needs no clause of its own: `release_status =
    'public'` already excludes it."""
    with session_ctx() as session:
        thing = session.get(Thing, well_with_one_water_level["thing"])
        thing.release_status = "embargoed"
        thing.release_at = TOMORROW
        session.commit()
        _refresh(session)

        assert _relations_naming(session, well_with_one_water_level["thing"]) == set()


def test_a_record_returns_when_its_embargo_is_lifted(well_with_one_water_level):
    """End to end: embargo, hidden; the date arrives, the job runs, the
    refresh follows, and the measurement is published."""
    with session_ctx() as session:
        observation = session.get(Observation, well_with_one_water_level["observation"])
        observation.release_status = "embargoed"
        observation.release_at = date.today()
        session.commit()
        _refresh(session)
        assert _relations_naming(session, well_with_one_water_level["thing"]) == set()

        lift_due_embargoes(session)
        _refresh(session)

        assert _relations_naming(session, well_with_one_water_level["thing"]) == {
            relation for relation, _ in WATER_LEVEL_RELATIONS
        }


def test_a_draft_measurement_is_still_published(well_with_one_water_level):
    """The migration adds an embargo clause, not a release-policy change.
    Observations sitting at `draft` reached these four relations before it and
    still do -- tightening that is a separate decision with its own row
    counts (see migration b4c5d6e7f8a9)."""
    with session_ctx() as session:
        observation = session.get(Observation, well_with_one_water_level["observation"])
        observation.release_status = "draft"
        session.commit()
        _refresh(session)

        assert _relations_naming(session, well_with_one_water_level["thing"]) == {
            relation for relation, _ in WATER_LEVEL_RELATIONS
        }
