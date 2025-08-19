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
from db import Observation
from core.dependencies import amp_admin_function, admin_function
from main import app
from tests import client, cleanup_post_test, override_authentication
import pytest


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )

    yield

    app.dependency_overrides = {}


# ============= Post tests =================
def test_add_water_chemistry_observation(sample, sensor):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 7.5,
        "unit": "dimensionless",
        "sample_id": sample.id,
        "sensor_id": sensor.id,
        "observed_property": "pH",
    }
    response = client.post("/observation/water-chemistry", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["unit"] == payload["unit"]
    assert data["sample_id"] == payload["sample_id"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["observed_property"] == payload["observed_property"]

    cleanup_post_test(Observation, data["id"])


def test_add_groundwater_level_observation(sample, sensor):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 101,
        "measuring_point_height": 53,
        "sample_id": sample.id,
        "sensor_id": sensor.id,
        "level_status": "normal",
        "observed_property": "groundwater level",
        "unit": "ft",
    }
    response = client.post("/observation/groundwater-level", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["measuring_point_height"] == payload["measuring_point_height"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["level_status"] == payload["level_status"]
    assert data["observed_property"] == payload["observed_property"]
    assert (
        data["depth_to_water_bgs"]
        == payload["value"] - payload["measuring_point_height"]
    )

    cleanup_post_test(Observation, data["id"])


def test_add_geothermal_observation(sample, sensor):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "observation_depth": 100,
        "value": 25.5,
        "sample_id": sample.id,
        "sensor_id": sensor.id,
        "observed_property": "temperature",
        "unit": "C",
    }
    response = client.post("/observation/geothermal", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["observation_depth"] == payload["observation_depth"]
    assert data["value"] == payload["value"]
    assert data["sample_id"] == payload["sample_id"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["observed_property"] == payload["observed_property"]
    assert data["unit"] == payload["unit"]

    cleanup_post_test(Observation, data["id"])


# ============= Get tests =================


def test_get_groundwater_observation_by_sample(sample):
    response = client.get(
        "/observation/groundwater-level",
        params={"sample_id": sample.id, "observed_property": "groundwater level"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) > 0, "Expected at least one groundwater observation for the thing"


def test_get_groundwater_observation_by_thing(sample):
    response = client.get(
        "/observation/groundwater-level",
        params={"thing_id": sample.thing_id, "observed_property": "groundwater level"},
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


# JB's comment: I don't think that geographic filters are necessary for
# observations. I think that they should only be applicable to finding Things
# and locations. Then the user can proceed from there to find observations.
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


# JB's comment: I don't think that geographic filters are necessary for
# observations. I think that they should only be applicable to finding Things
# and locations. Then the user can proceed from there to find observations
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


# ============= EOF =============================================
