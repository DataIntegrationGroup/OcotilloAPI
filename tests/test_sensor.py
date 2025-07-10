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
from tests import client


def test_add_sensor():
    response = client.post(
        "/sensor",
        json={
            "name": "Test Sensor",
            "equipment_type": "Pump",
            "model": "Model X",
            "serial_no": "123456",
            "date_installed": "2023-01-01T00:00:00",
            # "date_removed": None,
            "recording_interval": 60,
            "equipment_notes": "Test equipment",
            # "location_id": 2,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    # assert data["location_id"] == 2


def test_get_sensors():
    response = client.get("/sensor")
    assert response.status_code == 200
    data = response.json()
    # assert isinstance(items, list), "Expected a list of sensors"
    assert 'items' in data
    items = data['items']
    assert "id" in items[0], "Expected 'id' in sensor items"
    # assert "name" in items[0], "Expected 'name' in sensor items"
    # assert "equipment_type" in items[0], "Expected 'equipment_type' in sensor items"


def test_get_sensor():
    # Assuming the first sensor has an ID of 1
    response = client.get("/sensor/1")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data, "Expected 'id' in sensor data"
    assert data["id"] == 1, "Expected sensor ID to be 1"
    assert "name" in data, "Expected 'name' in sensor data"
    assert "equipment_type" in data, "Expected 'equipment_type' in sensor data"


# ============= EOF =============================================
