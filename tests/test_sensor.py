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
from core.dependencies import admin_function, editor_function, viewer_function
from db import Sensor
from main import app

# from schemas.sensor import ValidateSensor
from tests import (
    client,
    cleanup_post_test,
    cleanup_patch_test,
    override_authentication,
    groundwater_level_parameter_id,
)

import pytest
from datetime import timezone

# from pydantic import ValidationError


@pytest.fixture(scope="module", autouse=True)
def override_dependencies_fixture():
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# ====== VALIDATION tests ======================================================

# TODO: installation and removal dates were removed from the Sensor model, so these tests may no longer be relevant.

# def test_validate_datetime_installed_datetime_removed():
#     with pytest.raises(
#         ValidationError, match="datetime removed must be after datetime installed"
#     ):
#         ValidateSensor(
#             datetime_installed="2023-01-02T00:00:00Z",
#             datetime_removed="2023-01-01T00:00:00Z",
#         )


# ====== POST tests ============================================================


def test_add_sensor():
    payload = {
        "name": "Test Sensor 2",
        "sensor_type": "Pressure Transducer",
        "model": "Model X",
        "serial_no": "12345678",
        "pcn_number": "PCN-001",
        "owner_agency": "NMBGMR",
        "sensor_status": "In Service",
        "notes": "Test equipment",
        "release_status": "draft",
    }
    response = client.post("/sensor", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
    assert data["name"] == payload["name"]
    assert data["sensor_type"] == payload["sensor_type"]
    assert data["model"] == payload["model"]
    assert data["serial_no"] == payload["serial_no"]
    assert data["pcn_number"] == payload["pcn_number"]
    assert data["owner_agency"] == payload["owner_agency"]
    assert data["sensor_status"] == payload["sensor_status"]
    assert data["notes"] == payload["notes"]

    # cleanup after post test
    cleanup_post_test(Sensor, data["id"])


# ====== PATCH tests ===========================================================


def test_patch_sensor(sensor):
    payload = {
        "name": "patched name",
        "sensor_type": "Data Logger",
        "model": "patched model",
        "owner_agency": "USGS",
        "sensor_status": "In Repair",
        "release_status": "draft",
    }
    response = client.patch(f"/sensor/{sensor.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sensor.id
    assert data["name"] == payload["name"]
    assert data["sensor_type"] == payload["sensor_type"]
    assert data["model"] == payload["model"]
    assert data["owner_agency"] == payload["owner_agency"]
    assert data["sensor_status"] == payload["sensor_status"]
    assert data["release_status"] == payload["release_status"]

    # cleanup after patch test
    cleanup_patch_test(Sensor, payload, sensor)


def test_patch_sensor_404_not_found(sensor):
    bad_sensor_id = 99999
    payload = {"name": "patched name", "model": "patched model"}
    response = client.patch(f"/sensor/{bad_sensor_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sensor with ID {bad_sensor_id} not found."


# TODO: datetime_installed and datetime_removed were removed from the Sensor model, so these tests may no longer be relevant.

# def test_patch_sensor_409_conflicting_datetime_installed(sensor):
#     payload = {"datetime_installed": "2025-01-01T00:00:00Z"}
#     response = client.patch(f"/sensor/{sensor.id}", json=payload)
#     assert response.status_code == 409
#     data = response.json()
#     assert data["detail"][0]["loc"] == ["body", "datetime_installed"]
#     assert (
#         data["detail"][0]["msg"]
#         == f"new datetime installed must be before existing datetime removed of {sensor.datetime_removed}"
#     )
#     assert data["detail"][0]["type"] == "value_error"

# TODO: datetime_installed and datetime_removed were removed from the Sensor model, so these tests may no longer be relevant.

# def test_patch_sensor_409_conflicting_datetime_removed(sensor):
#     payload = {"datetime_removed": "2020-01-01T00:00:00Z"}
#     response = client.patch(f"/sensor/{sensor.id}", json=payload)
#     assert response.status_code == 409
#     data = response.json()
#     assert data["detail"][0]["loc"] == ["body", "datetime_removed"]
#     assert (
#         data["detail"][0]["msg"]
#         == f"new datetime removed must be after existing datetime installed of {sensor.datetime_installed}"
#     )
#     assert data["detail"][0]["type"] == "value_error"


# ====== GET tests =============================================================


def test_get_sensors(sensor):
    response = client.get("/sensor")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sensor.id
    assert data["items"][0]["created_at"] == sensor.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert data["items"][0]["release_status"] == sensor.release_status
    assert data["items"][0]["name"] == sensor.name
    assert data["items"][0]["sensor_type"] == sensor.sensor_type
    assert data["items"][0]["model"] == sensor.model
    assert data["items"][0]["serial_no"] == sensor.serial_no
    assert data["items"][0]["pcn_number"] == sensor.pcn_number
    assert data["items"][0]["owner_agency"] == sensor.owner_agency
    assert data["items"][0]["sensor_status"] == sensor.sensor_status
    assert data["items"][0]["notes"] == sensor.notes


def test_get_sensors_by_thing_id(
    sensor,
    sensor_to_water_well_thing_deployment,
    water_well_thing,
):
    response = client.get(f"/sensor?thing_id={water_well_thing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sensor.id
    assert data["items"][0]["created_at"] == sensor.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert data["items"][0]["release_status"] == sensor.release_status
    assert data["items"][0]["name"] == sensor.name
    assert data["items"][0]["sensor_type"] == sensor.sensor_type
    assert data["items"][0]["model"] == sensor.model
    assert data["items"][0]["serial_no"] == sensor.serial_no
    assert data["items"][0]["pcn_number"] == sensor.pcn_number
    assert data["items"][0]["owner_agency"] == sensor.owner_agency
    assert data["items"][0]["sensor_status"] == sensor.sensor_status
    assert data["items"][0]["notes"] == sensor.notes


def test_get_sensors_by_parameter_id(sensor, groundwater_level_observation):
    response = client.get(f"/sensor?parameter_id={groundwater_level_parameter_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sensor.id
    assert data["items"][0]["created_at"] == sensor.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert data["items"][0]["release_status"] == sensor.release_status
    assert data["items"][0]["name"] == sensor.name
    assert data["items"][0]["sensor_type"] == sensor.sensor_type
    assert data["items"][0]["model"] == sensor.model
    assert data["items"][0]["serial_no"] == sensor.serial_no
    assert data["items"][0]["pcn_number"] == sensor.pcn_number
    assert data["items"][0]["owner_agency"] == sensor.owner_agency
    assert data["items"][0]["sensor_status"] == sensor.sensor_status
    assert data["items"][0]["notes"] == sensor.notes


def test_get_sensor_by_id(sensor):
    response = client.get(f"/sensor/{sensor.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sensor.id
    assert data["created_at"] == sensor.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert data["release_status"] == sensor.release_status
    assert data["name"] == sensor.name
    assert data["sensor_type"] == sensor.sensor_type
    assert data["model"] == sensor.model
    assert data["serial_no"] == sensor.serial_no
    assert data["pcn_number"] == sensor.pcn_number
    assert data["owner_agency"] == sensor.owner_agency
    assert data["sensor_status"] == sensor.sensor_status
    assert data["notes"] == sensor.notes


def test_get_sensor_by_id_404_not_found(sensor):
    bad_sensor_id = 999999
    response = client.get(f"/sensor/{bad_sensor_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sensor with ID {bad_sensor_id} not found."


# ====== DELETE tests ==========================================================


def test_delete_sensor(second_sensor):
    response = client.delete(f"/sensor/{second_sensor.id}")
    assert response.status_code == 204

    # verify sensor is gone
    response = client.get(f"/sensor/{second_sensor.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sensor with ID {second_sensor.id} not found."


def test_delete_sensor_404_not_found(sensor):
    bad_sensor_id = 999999
    response = client.delete(f"/sensor/{bad_sensor_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sensor with ID {bad_sensor_id} not found."


# ============= EOF =============================================
