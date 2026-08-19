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
Watermark behaviour, including the property that makes backfill safe.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from automated_ingestion.ocotillo.loader import load_observations
from automated_ingestion.ocotillo.structs import ObservationRecord
from automated_ingestion.shared.watermark import (
    InMemoryWatermarkStore,
    PostgresWatermarkStore,
    resolve_start,
)
from db.engine import session_ctx
from db.parameter import Parameter
from db.transducer import TransducerObservation

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
FLOOR = datetime(2015, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def series(sensor_to_water_well_thing_deployment):
    """A deployment, its thing, and a parameter, cleaned up afterwards."""
    deployment = sensor_to_water_well_thing_deployment
    with session_ctx() as session:
        parameter_id = session.scalar(select(Parameter.id).limit(1))
        yield deployment.id, deployment.thing_id, parameter_id
        session.execute(
            delete(TransducerObservation).where(
                TransducerObservation.deployment_id == deployment.id
            )
        )
        session.commit()


def _records(count, start=START, value=10.0):
    return [
        ObservationRecord(
            external_point_id="sanacaciareach-40",
            observation_datetime=start + timedelta(minutes=5 * i),
            value=value,
            units="ft",
        )
        for i in range(count)
    ]


class TestPostgresWatermark:
    def test_unloaded_series_has_no_watermark(self, series):
        deployment_id, thing_id, parameter_id = series
        with session_ctx() as session:
            store = PostgresWatermarkStore(session)
            assert store.get(thing_id, parameter_id) is None

    def test_watermark_is_the_latest_observation(self, series):
        deployment_id, thing_id, parameter_id = series
        with session_ctx() as session:
            load_observations(
                session, _records(10), deployment_id, parameter_id, "draft"
            )
            store = PostgresWatermarkStore(session)
            assert store.get(thing_id, parameter_id) == START + timedelta(minutes=45)

    def test_backfilling_older_data_does_not_advance_it(self, series):
        # The property that makes backfill safe: a watermark derived from the
        # data cannot be moved forward by re-loading a window behind it. A
        # stored watermark has to be defended against this; a derived one
        # cannot have the problem.
        deployment_id, thing_id, parameter_id = series
        with session_ctx() as session:
            load_observations(
                session, _records(10), deployment_id, parameter_id, "draft"
            )
            store = PostgresWatermarkStore(session)
            before = store.get(thing_id, parameter_id)

            older = _records(10, start=START - timedelta(days=365))
            load_observations(session, older, deployment_id, parameter_id, "draft")

            assert store.get(thing_id, parameter_id) == before

    def test_reloading_the_same_window_does_not_move_it(self, series):
        deployment_id, thing_id, parameter_id = series
        with session_ctx() as session:
            load_observations(
                session, _records(5), deployment_id, parameter_id, "draft"
            )
            store = PostgresWatermarkStore(session)
            before = store.get(thing_id, parameter_id)
            load_observations(
                session, _records(5), deployment_id, parameter_id, "draft"
            )
            assert store.get(thing_id, parameter_id) == before


class TestResolveStart:
    def test_floor_applies_only_to_a_new_series(self):
        assert resolve_start(InMemoryWatermarkStore(), 1, 2, FLOOR) == FLOOR

    def test_watermark_wins_over_the_floor(self):
        # The floor is not a backfill lever: lowering it must not re-fetch
        # history for a series that has already advanced past it.
        store = InMemoryWatermarkStore({(1, 2): START})
        assert resolve_start(store, 1, 2, FLOOR) == START

    def test_a_floor_ahead_of_the_watermark_does_not_win_either(self):
        store = InMemoryWatermarkStore({(1, 2): START})
        ahead = START + timedelta(days=365)
        assert resolve_start(store, 1, 2, ahead) == START


# ============= EOF =============================================
