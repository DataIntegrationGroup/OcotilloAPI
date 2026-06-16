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
Tests for the transducer_daily_data materialized view, which aggregates raw
transducer observations into one row per well, parameter, day, and QC status.
"""

from datetime import date

import pytest
from sqlalchemy import delete, text

from db import Deployment, Sensor, Thing, TransducerObservation
from db.engine import session_ctx
from tests import get_parameter_id

POINT_ID = "TDD-TEST-0001"


def _refresh_view(session):
    session.execute(text("REFRESH MATERIALIZED VIEW transducer_daily_data"))
    session.commit()


@pytest.fixture(scope="module")
def transducer_well():
    """A well with a transducer deployment and two days of observations."""
    with session_ctx() as session:
        thing = Thing(name=POINT_ID, thing_type="water well", release_status="public")
        session.add(thing)
        session.flush()

        sensor = Sensor(
            name=f"{POINT_ID}-transducer",
            sensor_type="Pressure Transducer",
            release_status="public",
        )
        session.add(sensor)
        session.flush()

        deployment = Deployment(
            thing_id=thing.id,
            sensor_id=sensor.id,
            installation_date="2024-01-01",
            release_status="public",
        )
        session.add(deployment)
        session.flush()

        parameter_id = get_parameter_id("groundwater level", "Field Parameter")

        observations = [
            # Day 1: three QCed readings -> avg 12.0, min 10.0, max 14.0.
            ("2024-03-15T06:00:00Z", 10.0, "public", 8.5),
            ("2024-03-15T12:00:00Z", 12.0, "public", 9.0),
            ("2024-03-15T18:00:00Z", 14.0, "public", 9.5),
            # Day 1: one un-QCed reading -> separate row.
            ("2024-03-15T13:00:00Z", 99.0, "private", None),
            # Day 2: two QCed readings -> avg 21.0.
            ("2024-03-16T06:00:00Z", 20.0, "public", None),
            ("2024-03-16T18:00:00Z", 22.0, "public", None),
        ]
        for dt, value, release_status, temperature in observations:
            session.add(
                TransducerObservation(
                    deployment_id=deployment.id,
                    parameter_id=parameter_id,
                    observation_datetime=dt,
                    value=value,
                    release_status=release_status,
                    nma_waterlevelscontinuous_pressure_temperature_water=temperature,
                )
            )
        session.commit()
        thing_id = thing.id
        sensor_id = sensor.id

        _refresh_view(session)

    yield thing_id

    with session_ctx() as session:
        # Thing delete cascades to the deployment and its observations.
        session.execute(delete(Thing).where(Thing.id == thing_id))
        session.execute(delete(Sensor).where(Sensor.id == sensor_id))
        session.commit()
        _refresh_view(session)


def _fetch_rows(session, thing_id):
    return (
        session.execute(
            text(
                "SELECT * FROM transducer_daily_data "
                "WHERE thing_id = :thing_id ORDER BY date_measured, qced"
            ),
            {"thing_id": thing_id},
        )
        .mappings()
        .all()
    )


def test_transducer_daily_data_aggregation(transducer_well):
    with session_ctx() as session:
        rows = _fetch_rows(session, transducer_well)

    assert len(rows) == 3

    day1_private, day1_public, day2_public = rows

    assert day1_private["point_id"] == POINT_ID
    assert day1_private["parameter_name"] == "groundwater level"
    assert day1_private["date_measured"] == date(2024, 3, 15)
    assert day1_private["qced"] is False
    assert day1_private["measurement_count"] == 1
    assert day1_private["depth_to_water_bgs"] == pytest.approx(99.0)

    assert day1_public["date_measured"] == date(2024, 3, 15)
    assert day1_public["qced"] is True
    assert day1_public["measurement_count"] == 3
    assert day1_public["depth_to_water_bgs"] == pytest.approx(12.0)
    assert day1_public["depth_to_water_bgs_min"] == pytest.approx(10.0)
    assert day1_public["depth_to_water_bgs_max"] == pytest.approx(14.0)
    assert day1_public["temperature_water"] == pytest.approx(9.0)

    assert day2_public["date_measured"] == date(2024, 3, 16)
    assert day2_public["qced"] is True
    assert day2_public["measurement_count"] == 2
    assert day2_public["depth_to_water_bgs"] == pytest.approx(21.0)
    assert day2_public["temperature_water"] is None


def test_transducer_daily_data_concurrent_refresh(transducer_well):
    # The unique index on (thing_id, parameter_id, date_measured, qced) must
    # support CONCURRENTLY, which the refresh CLI uses in production.
    from db.engine import engine

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(
            text("REFRESH MATERIALIZED VIEW CONCURRENTLY transducer_daily_data")
        )

    with session_ctx() as session:
        rows = _fetch_rows(session, transducer_well)
    assert len(rows) == 3


# ============= EOF =============================================
