# ===============================================================================
# Copyright 2025 ross
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
from datetime import datetime

import pytest

from models import get_db_session, sqlalchemy_sessionmaker
from models.base import SampleLocation, Well
from models.collabnet import CollaborativeNetworkWell
from models.timeseries import WellTimeseries, GroundwaterLevelObservation
from tests import client


def test_add_collabnet_well():
    response = client.post(
        "/collabnet/add",
        json={
            "well_id": 2,
            "actively_monitored": True,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["well_id"] == 2
    assert data["actively_monitored"] is True


def test_collabnet_wells():
    response = client.get("/collabnet/location_feature_collection")
    assert response.status_code == 200


@pytest.fixture(scope="function")
def add_timeseries_data():
    """Fixture to add timeseries data for testing."""
    session = sqlalchemy_sessionmaker()
    wts = WellTimeseries(well_id=2)
    session.add(wts)
    for i in range(10):
        obs = GroundwaterLevelObservation(
            value=10 + i,
            timestamp=datetime.strptime(f"2023-01-{i+1}T00:00:00", "%Y-%m-%dT%H:%M:%S"),
        )
        obs.timeseries = wts
        session.add(obs)

    # add another well
    location = SampleLocation(
        name="Collabnet Test Location", point="SRID=4326;POINT(0 0)"
    )
    well = Well()
    well.location = location

    collabnet = CollaborativeNetworkWell(well=well, actively_monitored=False)
    session.add(collabnet)
    session.commit()

    yield

    # Teardown: remove the added data
    for obs in wts.observations:
        session.delete(obs)
    session.delete(wts)
    session.delete(collabnet)
    session.delete(well)
    session.delete(location)
    session.commit()


def test_collabnet_stats(add_timeseries_data):
    response = client.get("/collabnet/stats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "total_wells" in data
    assert data["total_wells"] == 2
    assert "actively_monitored_wells" in data

    assert data["actively_monitored_wells"] == 1
    # assert "inactive_wells" in data


# ============= EOF =============================================
