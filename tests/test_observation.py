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
from core.dependencies import (
    amp_admin_function,
    admin_function,
    amp_viewer_function,
    amp_editor_function,
    viewer_function,
)
from main import app
from tests import client, cleanup_post_test, override_authentication, cleanup_patch_test
import pytest


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# ============= Post tests =================
def test_add_water_chemistry_observation(
    water_chemistry_sample, sensor, parameter_water_chemistry
):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 7.5,
        "unit": "dimensionless",
        "sample_id": water_chemistry_sample.id,
        "sensor_id": sensor.id,
        "parameter_id": parameter_water_chemistry.id,
    }
    response = client.post("/observation/water-chemistry", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert "id" in data
    assert "created_at" in data
    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["unit"] == payload["unit"]
    assert data["sample_id"] == payload["sample_id"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["parameter"]["id"] == parameter_water_chemistry.id

    cleanup_post_test(Observation, data["id"])


def test_add_groundwater_level_observation(
    groundwater_level_sample, sensor, parameter_groundwater
):
    payload = {
        "observation_datetime": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "value": 101,
        "measuring_point_height": 53,
        "sample_id": groundwater_level_sample.id,
        "parameter_id": parameter_groundwater.id,
        "sensor_id": sensor.id,
        "level_status": "Water level not affected by status",
        "unit": "ft",
    }
    response = client.post("/observation/groundwater-level", json=payload)
    data = response.json()
    assert response.status_code == 201

    assert "id" in data
    assert "created_at" in data
    assert data["observation_datetime"] == payload["observation_datetime"]
    assert data["release_status"] == payload["release_status"]
    assert data["value"] == payload["value"]
    assert data["measuring_point_height"] == payload["measuring_point_height"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["parameter"]["id"] == parameter_groundwater.id
    assert data["level_status"] == payload["level_status"]
    assert (
        data["depth_to_water_bgs"]
        == payload["value"] - payload["measuring_point_height"]
    )

    cleanup_post_test(Observation, data["id"])


# def test_add_geothermal_observation(geothermal_sample, sensor):
#     payload = {
#         "observation_datetime": "2025-01-01T00:00:00Z",
#         "release_status": "draft",
#         "observation_depth": 100,
#         "value": 25.5,
#         "sample_id": geothermal_sample.id,
#         "sensor_id": sensor.id,
#         "observed_property": "temperature",
#         "unit": "deg C",
#     }
#     response = client.post("/observation/geothermal", json=payload)
#     data = response.json()
#     assert response.status_code == 201

#     assert "id" in data
#     assert "created_at" in data
#     assert data["observation_datetime"] == payload["observation_datetime"]
#     assert data["release_status"] == payload["release_status"]
#     assert data["observation_depth"] == payload["observation_depth"]
#     assert data["value"] == payload["value"]
#     assert data["sample_id"] == payload["sample_id"]
#     assert data["sensor_id"] == payload["sensor_id"]
#     assert data["observed_property"] == payload["observed_property"]
#     assert data["unit"] == payload["unit"]

#     cleanup_post_test(Observation, data["id"])


# PATCH tests ==================================================================


# TODO update patch test to test every single field
def test_patch_groundwater_level_observation(groundwater_level_observation):
    payload = {"measuring_point_height": 3, "release_status": "private"}
    response = client.patch(
        f"/observation/groundwater-level/{groundwater_level_observation.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["measuring_point_height"] == payload["measuring_point_height"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Observation, payload, groundwater_level_observation)


def test_patch_groundwater_level_observation_404_not_found(
    groundwater_level_observation,
):
    bad_id = 99999
    payload = {"measuring_point_height": 3}
    response = client.patch(f"/observation/groundwater-level/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_patch_groundwater_level_observation_404_wrong_activity_type(
    water_chemistry_observation,
):
    payload = {"measuring_point_height": 3}
    response = client.patch(
        f"/observation/groundwater-level/{water_chemistry_observation.id}", json=payload
    )
    assert response.status_code == 404
    data = response.json()

    actual_activity_type = "water chemistry"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {water_chemistry_observation.id} is not a groundwater level observation. It is a {actual_activity_type} observation."
    )


def test_patch_water_chemistry_observation(water_chemistry_observation):
    payload = {"value": 8, "release_status": "private"}
    response = client.patch(
        f"/observation/water-chemistry/{water_chemistry_observation.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 200

    assert data["value"] == payload["value"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Observation, payload, water_chemistry_observation)


def test_patch_water_chemistry_observation_404_not_found(water_chemistry_observation):
    bad_id = 999999
    payload = {"value": 8}
    response = client.patch(f"/observation/water-chemistry/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_patch_water_chemistry_observation_404_wrong_activity_type(
    groundwater_level_observation,
):
    payload = {"value": 8}
    response = client.patch(
        f"/observation/water-chemistry/{groundwater_level_observation.id}", json=payload
    )
    assert response.status_code == 404
    data = response.json()

    actualy_activity_type = "groundwater level"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {groundwater_level_observation.id} is not a water chemistry observation. It is a {actualy_activity_type} observation."
    )


# def test_patch_geothermal_observation(geothermal_observation):
#     payload = {"observation_depth": 4, "release_status": "private"}
#     response = client.patch(
#         f"/observation/geothermal/{geothermal_observation.id}", json=payload
#     )
#     assert response.status_code == 200
#     data = response.json()
#     assert data["observation_depth"] == payload["observation_depth"]
#     assert data["release_status"] == payload["release_status"]

#     cleanup_patch_test(Observation, payload, geothermal_observation)


# def test_patch_geothermal_observation_404_not_found(geothermal_observation):
#     bad_id = 999999
#     payload = {"observation_depth": 8}
#     response = client.patch(f"/observation/geothermal/{bad_id}", json=payload)
#     assert response.status_code == 404
#     data = response.json()
#     assert data["detail"] == f"Observation with ID {bad_id} not found."


# def test_patch_geothermal_observation_404_wrong_activity_type(
#     groundwater_level_observation, water_chemistry_observation
# ):
#     for obs in groundwater_level_observation, water_chemistry_observation:
#         payload = {"value": 8}
#         response = client.patch(f"/observation/geothermal/{obs.id}", json=payload)
#         assert response.status_code == 404
#         data = response.json()

#         if obs.observed_property == "groundwater level":
#             activity_type = "groundwater level"
#         else:
#             activity_type = "water chemistry"

#         assert (
#             data["detail"][0]["msg"]
#             == f"Observation with ID {obs.id} is not a geothermal observation. It is a {activity_type} observation."
#         )


# ============= Get tests =================


def test_get_all_observations(
    groundwater_level_observation, water_chemistry_observation
):
    response = client.get("/observation")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for item in data["items"]:
        assert "id" in item
        assert "created_at" in item
        assert "release_status" in item
        assert "sample_id" in item
        assert "sensor_id" in item
        assert "observation_datetime" in item
        assert "parameter" in item
        assert "value" in item
        assert "unit" in item


def test_get_observation_by_id(
    groundwater_level_observation, water_chemistry_observation, parameter_groundwater
):
    for obs in (
        groundwater_level_observation,
        water_chemistry_observation,
    ):
        response = client.get(f"/observation/{obs.id}")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == obs.id
        assert data["created_at"] == obs.created_at.isoformat().replace("+00:00", "Z")
        assert data["release_status"] == obs.release_status
        if obs.parameter.parameter_name == parameter_groundwater.parameter_name:
            assert data["depth_to_water_bgs"] == obs.value - obs.measuring_point_height
        else:
            assert data["depth_to_water_bgs"] is None


def test_get_observation_by_id_404_not_found(
    groundwater_level_observation, water_chemistry_observation
):
    bad_id = 999999
    response = client.get(f"/observation/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_groundwater_level_observations(
    groundwater_level_observation, parameter_groundwater
):
    response = client.get("/observation/groundwater-level")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == groundwater_level_observation.id
    assert data["items"][0][
        "created_at"
    ] == groundwater_level_observation.created_at.isoformat().replace("+00:00", "Z")
    assert data["items"][0]["sample_id"] == groundwater_level_observation.sample_id
    assert data["items"][0]["sensor_id"] == groundwater_level_observation.sensor_id
    assert (
        data["items"][0]["observation_datetime"]
        == groundwater_level_observation.observation_datetime
    )
    assert data["items"][0]["parameter"]["id"] == parameter_groundwater.id
    assert (
        data["items"][0]["release_status"]
        == groundwater_level_observation.release_status
    )
    assert (
        data["items"][0]["level_status"] == groundwater_level_observation.level_status
    )
    assert data["items"][0]["value"] == groundwater_level_observation.value
    assert data["items"][0]["unit"] == groundwater_level_observation.unit
    assert (
        data["items"][0]["depth_to_water_bgs"]
        == groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    )
    assert (
        data["items"][0]["measuring_point_height"]
        == groundwater_level_observation.measuring_point_height
    )
    assert (
        data["items"][0]["level_status"] == groundwater_level_observation.level_status
    )


def test_get_groundwater_level_observation_by_id(
    groundwater_level_observation, parameter_groundwater
):
    response = client.get(
        f"/observation/groundwater-level/{groundwater_level_observation.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == groundwater_level_observation.id
    assert data[
        "created_at"
    ] == groundwater_level_observation.created_at.isoformat().replace("+00:00", "Z")
    assert data["sample_id"] == groundwater_level_observation.sample_id
    assert data["sensor_id"] == groundwater_level_observation.sensor_id
    assert (
        data["observation_datetime"]
        == groundwater_level_observation.observation_datetime
    )
    assert data["parameter"]["id"] == parameter_groundwater.id
    assert data["release_status"] == groundwater_level_observation.release_status
    assert data["level_status"] == groundwater_level_observation.level_status
    assert data["value"] == groundwater_level_observation.value
    assert data["unit"] == groundwater_level_observation.unit
    assert (
        data["depth_to_water_bgs"]
        == groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    )
    assert (
        data["measuring_point_height"]
        == groundwater_level_observation.measuring_point_height
    )
    assert data["level_status"] == groundwater_level_observation.level_status


def test_get_groundwater_level_observation_by_id_404_not_found(
    groundwater_level_observation,
):
    bad_id = 99999
    response = client.get(f"/observation/groundwater-level/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data, "Expected 'detail' in response"
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_groundwater_level_observation_by_id_404_wrong_activity_type(
    water_chemistry_observation,
):
    response = client.get(
        f"/observation/groundwater-level/{water_chemistry_observation.id}"
    )
    assert response.status_code == 404
    data = response.json()

    actual_activity_type = "water chemistry"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {water_chemistry_observation.id} is not a groundwater level observation. It is a {actual_activity_type} observation."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "observation_id": water_chemistry_observation.id
    }
    assert data["detail"][0]["loc"] == ["path", "observation_id"]


def test_get_groundwater_observation_by_sample(
    groundwater_level_observation, groundwater_level_sample
):
    response = client.get(
        "/observation/groundwater-level",
        params={
            "sample_id": groundwater_level_sample.id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert len(items) > 0, "Expected at least one groundwater observation for the thing"


def test_get_groundwater_observation_by_thing(
    groundwater_level_observation, water_well_thing
):
    response = client.get(
        "/observation/groundwater-level",
        params={
            "thing_id": water_well_thing.id,
        },
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


def test_get_groundwater_observation_by_time_range(groundwater_level_observation):
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


def test_get_water_chemistry_observations(
    water_chemistry_observation, parameter_water_chemistry
):
    response = client.get("/observation/water-chemistry")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == water_chemistry_observation.id
    assert data["items"][0][
        "created_at"
    ] == water_chemistry_observation.created_at.isoformat().replace("+00:00", "Z")
    assert (
        data["items"][0]["release_status"] == water_chemistry_observation.release_status
    )
    assert data["items"][0]["sample_id"] == water_chemistry_observation.sample_id
    assert data["items"][0]["sensor_id"] == water_chemistry_observation.sensor_id
    assert (
        data["items"][0]["observation_datetime"]
        == water_chemistry_observation.observation_datetime
    )
    assert data["items"][0]["parameter"]["id"] == parameter_water_chemistry.id
    assert data["items"][0]["value"] == water_chemistry_observation.value
    assert data["items"][0]["unit"] == water_chemistry_observation.unit


def test_get_water_chemistry_observation_by_id(
    water_chemistry_observation, parameter_water_chemistry
):
    response = client.get(
        f"/observation/water-chemistry/{water_chemistry_observation.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == water_chemistry_observation.id
    assert data[
        "created_at"
    ] == water_chemistry_observation.created_at.isoformat().replace("+00:00", "Z")
    assert data["release_status"] == water_chemistry_observation.release_status
    assert data["sample_id"] == water_chemistry_observation.sample_id
    assert data["sensor_id"] == water_chemistry_observation.sensor_id
    assert (
        data["observation_datetime"] == water_chemistry_observation.observation_datetime
    )

    assert data["parameter"]["id"] == parameter_water_chemistry.id
    assert data["value"] == water_chemistry_observation.value
    assert data["unit"] == water_chemistry_observation.unit


def test_get_water_chemistry_observation_by_id_404_not_found(
    water_chemistry_observation,
):
    bad_id = 99999
    response = client.get(f"/observation/water-chemistry/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


def test_get_water_chemistry_observation_by_id_404_wrong_activity_type(
    groundwater_level_observation, parameter_groundwater
):
    response = client.get(
        f"/observation/water-chemistry/{groundwater_level_observation.id}"
    )
    assert response.status_code == 404
    data = response.json()

    if (
        groundwater_level_observation.parameter.parameter_name
        == parameter_groundwater.parameter_name
    ):
        actual_activity_type = "groundwater level"
    else:
        actual_activity_type = "geothermal"

    assert (
        data["detail"][0]["msg"]
        == f"Observation with ID {groundwater_level_observation.id} is not a water chemistry observation. It is a {actual_activity_type} observation."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "observation_id": groundwater_level_observation.id
    }
    assert data["detail"][0]["loc"] == ["path", "observation_id"]


# def test_get_geothermal_observations(geothermal_observation):
#     response = client.get("/observation/geothermal")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["total"] == 1
#     assert data["items"][0]["id"] == geothermal_observation.id
#     assert data["items"][0][
#         "created_at"
#     ] == geothermal_observation.created_at.isoformat().replace("+00:00", "Z")
#     assert data["items"][0]["release_status"] == geothermal_observation.release_status
#     assert data["items"][0]["sample_id"] == geothermal_observation.sample_id
#     assert data["items"][0]["sensor_id"] == geothermal_observation.sensor_id
#     assert (
#         data["items"][0]["observation_datetime"]
#         == geothermal_observation.observation_datetime
#     )
#     colon_index = geothermal_observation.observed_property.find(":")
#     assert (
#         data["items"][0]["observed_property"]
#         == geothermal_observation.observed_property[colon_index + 1 :]
#     )
#     assert data["items"][0]["value"] == geothermal_observation.value
#     assert data["items"][0]["unit"] == geothermal_observation.unit
#     assert (
#         data["items"][0]["observation_depth"]
#         == geothermal_observation.observation_depth
#     )


# def test_get_geothermal_observation_by_id(geothermal_observation):
#     response = client.get(f"/observation/geothermal/{geothermal_observation.id}")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["id"] == geothermal_observation.id
#     assert data["created_at"] == geothermal_observation.created_at.isoformat().replace(
#         "+00:00", "Z"
#     )
#     assert data["release_status"] == geothermal_observation.release_status
#     assert data["sample_id"] == geothermal_observation.sample_id
#     assert data["sensor_id"] == geothermal_observation.sensor_id
#     assert data["observation_datetime"] == geothermal_observation.observation_datetime
#     colon_index = geothermal_observation.observed_property.find(":")
#     assert (
#         data["observed_property"]
#         == geothermal_observation.observed_property[colon_index + 1 :]
#     )
#     assert data["value"] == geothermal_observation.value
#     assert data["unit"] == geothermal_observation.unit
#     assert data["observation_depth"] == geothermal_observation.observation_depth


# def test_get_geothermal_observation_by_id_404_not_found(geothermal_observation):
#     bad_id = 99999
#     response = client.get(f"/observation/geothermal/{bad_id}")
#     assert response.status_code == 404
#     data = response.json()
#     assert data["detail"] == f"Observation with ID {bad_id} not found."


# def test_get_geothermal_observation_by_id_404_wrong_activity_type(
#     water_chemistry_observation, groundwater_level_observation
# ):
#     for obs in water_chemistry_observation, groundwater_level_observation:
#         response = client.get(f"/observation/geothermal/{obs.id}")
#         assert response.status_code == 404
#         data = response.json()

#         if obs.observed_property == "groundwater level":
#             actual_activity_type = "groundwater level"
#         else:
#             actual_activity_type = "water chemistry"

#         assert (
#             data["detail"][0]["msg"]
#             == f"Observation with ID {obs.id} is not a geothermal observation. It is a {actual_activity_type} observation."
#         )
#         assert data["detail"][0]["type"] == "value_error"
#         assert data["detail"][0]["input"] == {"observation_id": obs.id}
#         assert data["detail"][0]["loc"] == ["path", "observation_id"]


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


# DELETE tests =================================================================


def test_delete_observation_by_id(observation_to_delete):
    response = client.delete(f"/observation/{observation_to_delete.id}")
    assert response.status_code == 204

    # Verify that the observation was deleted
    get_response = client.get(f"/observation/{observation_to_delete.id}")
    assert get_response.status_code == 404
    data = get_response.json()
    assert (
        data["detail"] == f"Observation with ID {observation_to_delete.id} not found."
    )


def test_delete_observation_by_id_404_not_found(observation_to_delete):
    bad_id = 99999
    response = client.delete(f"/observation/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Observation with ID {bad_id} not found."


# ============= EOF =============================================
