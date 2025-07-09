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
from db import Sensor
from db.engine import get_db_session
from db.series.series import Series
from tests import client
import pytest


# ============= Post tests =================

@pytest.fixture(autouse=True)
def series():
    session = next(get_db_session())

    sensor = Sensor(name="Test Sensor")
    session.add(sensor)
    session.commit()
    session.refresh(sensor)


    session.add(Series(name="Test Series",
                       thing_id=1,
                       sensor_id=sensor.id,
                       unit="ft",
                       observed_property="groundwater level",))
    session.commit()
    yield
    session.close()


def test_add_observation():
    response = client.post("/observation",
                           json={"series_id": 1,
                                 'observation_timestamp': "2025-01-01T00:00:00Z",
                                 "release_status": "draft"})
    assert response.status_code == 201


def test_add_groundwater_observation():
    response = client.post("/observation/groundwater-level",
                           json={"observation_id": 1,
                                 "depth_to_water": 10,
                                 "measuring_point_height": 5
                                 })
    assert response.status_code == 201
    data = response.json()
    assert data["observation_id"] == 1


def test_add_groundwater_observation_direct():
    response = client.post("/observation/groundwater-level",
                           json={"series_id": 1,
                                 'observation_timestamp': "2025-01-01T00:00:00Z",
                                 "release_status": "draft",
                                 "depth_to_water": 101,
                                 "measuring_point_height": 53
                                 })
    assert response.status_code == 201
    data = response.json()
    assert data["observation_id"] == 2
    assert data["depth_to_water"] == 101
    assert data["measuring_point_height"] == 53


def test_add_geothermal_observation():
    response = client.post("/observation/geothermal",
                           json={"observation_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["observation_id"] == 1


@pytest.mark.skip(reason="not implemented yet")
def test_add_geochemical_observation():
    response = client.post("/observation/geochemical",
                           json={"observation_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["observation_id"] == 1

# ============= Get tests =================

def test_get_observation():
    pass
# ============= EOF =============================================
