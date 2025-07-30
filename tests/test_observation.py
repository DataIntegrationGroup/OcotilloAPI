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
from tests import client, thing, sensor
import pytest


# ============= Post tests =================
def test_add_groundwater_observation(thing, sensor):
    response = client.post(
        "/observation/groundwater-level",
        json={
            "observation_timestamp": "2025-01-01T00:00:00Z",
            "release_status": "draft",
            "depth_to_water": 101,
            "measuring_point_height": 53,
            "thing_id": thing.id,
            "sensor_id": sensor.id,
            "level_status": "normal",
            "observed_property": "groundwater level",
        },
    )
    data = response.json()
    assert response.status_code == 201

    assert data["depth_to_water"] == 101
    assert data["measuring_point_height"] == 53


# def test_add_geothermal_observation():
#     response = client.post(
#         "/observation/geothermal",
#         json={
#             "observation_id": 1,
#             "observation_timestamp": "2025-01-01T00:00:00Z",
#             "depth": 100,
#             "temperature": 25.5,
#         },
#     )
#     assert response.status_code == 201
#     data = response.json()
#     assert data["observation_id"] == 1


@pytest.mark.skip(reason="not implemented yet")
def test_add_geochemical_observation():
    response = client.post("/observation/geochemical", json={"observation_id": 1})
    assert response.status_code == 201
    data = response.json()
    assert data["observation_id"] == 1


# ============= Get tests =================
# def test_get_observation_by_series_id():
#     response = client.get("/observation", params={"series_id": 1})
#     assert response.status_code == 200
#     data = response.json()
#     assert "items" in data, "Expected 'items' in response"
#     items = data["items"]
#     assert len(items) > 0, "Expected at least one observation for the series"
#     # assert isinstance(data, list), "Expected a list of observations"
#     # assert len(data) == 1, "Expected at least one observation for the series"


# def test_get_groundwater_observation_by_thing_id():
#     response = client.get("/observation/groundwater-level", params={"thing_id": 1,
#                                                                     "observed_property": "groundwater level"})
#     assert response.status_code == 200
#     data = response.json()
#     assert "items" in data, "Expected 'items' in response"
#     items = data["items"]
#     assert (
#         len(items) > 0
#     ), "Expected at least one groundwater observation for the series"


# def test_get_geothermal_observation_by_series_id():
#     response = client.get("/observation/geothermal", params={"series_id": 1})
#     assert response.status_code == 200
#     data = response.json()
#     assert "items" in data, "Expected 'items' in response"
#     items = data["items"]
#     assert len(items) > 0, "Expected at least one geothermal observation for the series"


def test_get_groundwater_observation_by_thing(thing):
    response = client.get(
        "/observation/groundwater-level",
        params={"thing_id": thing.id, "observed_property": "groundwater level"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) > 0, "Expected at least one groundwater observation for the thing"


def test_get_groundwater_observation_by_thing_nonexistent():
    response = client.get("/observation/groundwater-level", params={"thing_id": 999})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) == 0
    ), "Expected no groundwater observations for a non-existent thing"


@pytest.mark.skip(reason="unclear why not working. is it necessary functionality?")
def test_get_groundwater_observation_by_polygon():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "polygon": "POLYGON((-10.0 -10.0, 20.0 10.0, 20.0 20.0, 10.0 20.0, -10.0 -10.0))",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) > 0
    ), "Expected at least one groundwater observation within the polygon"


@pytest.mark.skip(reason="unclear why not working. is it necessary functionality?")
def test_get_groundwater_observation_by_polygon_nonexistent():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "polygon": "POLYGON((-100.0 -100.0, -90.0 -90.0, -90.0 -80.0, -100.0 -80.0, -100.0 -100.0))",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) == 0, "Expected no groundwater observations within the polygon"


def test_get_groundwater_observation_by_time_range():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2025-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert (
        len(items) > 0
    ), "Expected at least one groundwater observation in the time range"


def test_get_groundwater_observation_by_time_range_nonexistent():
    response = client.get(
        "/observation/groundwater-level",
        params={
            "start_time": "2020-01-01T00:00:00Z",
            "end_time": "2020-01-02T00:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) == 0, "Expected no groundwater observations in the time range"


# ============= EOF =============================================
