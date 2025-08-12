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
from tests import client, cleanup_post_test

# ====== POST tests ============================================================


def test_add_sensor():
    payload = {
        "name": "Test Sensor 2",
        "model": "Model X",
        "serial_no": "12345678",
        "datetime_installed": "2024-01-01T00:00:00Z",
        "datetime_removed": None,
        "recording_interval": 60,
        "notes": "Test equipment",
    }
    response = client.post("/sensor", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == payload["name"]
    assert data["model"] == payload["model"]
    assert data["serial_no"] == payload["serial_no"]
    assert data["datetime_installed"] == payload["datetime_installed"]
    assert data["datetime_removed"] == payload["datetime_removed"]
    assert data["recording_interval"] == payload["recording_interval"]
    assert data["notes"] == payload["notes"]

    # cleanup after post test
    cleanup_post_test(Sensor, data["id"])


# ====== GET tests =============================================================


def test_get_sensors(sensor):
    response = client.get("/sensor")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sensor.id
    assert data["items"][0]["name"] == sensor.name
    assert data["items"][0]["model"] == sensor.model
    assert data["items"][0]["serial_no"] == sensor.serial_no
    assert data["items"][0]["datetime_installed"] == sensor.datetime_installed
    assert data["items"][0]["datetime_removed"] == sensor.datetime_removed
    assert data["items"][0]["recording_interval"] == sensor.recording_interval
    assert data["items"][0]["notes"] == sensor.notes


def test_get_sensor_by_id(sensor):
    response = client.get(f"/sensor/{sensor.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sensor.id, "Expected sensor ID to match"
    assert data["name"] == sensor.name, "Expected sensor name to match"
    assert data["model"] == sensor.model, "Expected sensor model to match"
    assert data["serial_no"] == sensor.serial_no, "Expected sensor serial_no to match"
    assert (
        data["datetime_installed"] == sensor.datetime_installed
    ), "Expected sensor datetime_installed to match"
    assert (
        data["datetime_removed"] == sensor.datetime_removed
    ), "Expected sensor datetime_removed to match"
    assert (
        data["recording_interval"] == sensor.recording_interval
    ), "Expected sensor recording_interval to match"
    assert data["notes"] == sensor.notes, "Expected sensor notes to match"


# ============= EOF =============================================
