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
from geoalchemy2.shape import to_shape
import pytest

from core.dependencies import admin_function, editor_function, viewer_function
from db import Location
from main import app
from tests import client, override_authentication, cleanup_post_test, cleanup_patch_test


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


#  ============= Post tests for locations ======================================


def test_add_location():
    payload = {
        "name": "test location",
        "notes": "these are some test notes",
        "point": "POINT Z (10.1 10.1 0)",
        "release_status": "draft",
        "elevation_accuracy": 1.0,
        "elevation_method": "GPS",
        "coordinate_accuracy": 5.0,
        "coordinate_method": "GPS",
    }
    response = client.post("/location", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["name"] == payload["name"]
    assert data["notes"] == payload["notes"]
    assert data["point"] == payload["point"]
    assert data["release_status"] == payload["release_status"]
    assert data["elevation_accuracy"] == payload["elevation_accuracy"]
    assert data["elevation_method"] == payload["elevation_method"]
    assert data["coordinate_accuracy"] == payload["coordinate_accuracy"]
    assert data["coordinate_method"] == payload["coordinate_method"]

    # cleanup after test
    cleanup_post_test(Location, data["id"])


#  ============= Patch tests for locations =====================================


def test_update_location(location):
    payload = {
        "name": "patched name",
        "notes": "these are some patched notes",
        "point": "POINT Z (10.1 20.2 0)",
        "release_status": "draft",
        "elevation_accuracy": 2.0,
        "elevation_method": "Total Station",
        "coordinate_accuracy": 10.0,
        "coordinate_method": "Total Station",
    }
    response = client.patch(f"/location/{location.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == location.id
    assert data["name"] == payload["name"]
    assert data["notes"] == payload["notes"]
    assert data["point"] == payload["point"]
    assert data["release_status"] == payload["release_status"]
    assert data["elevation_accuracy"] == payload["elevation_accuracy"]
    assert data["elevation_method"] == payload["elevation_method"]
    assert data["coordinate_accuracy"] == payload["coordinate_accuracy"]
    assert data["coordinate_method"] == payload["coordinate_method"]

    # cleanup after test
    cleanup_patch_test(Location, payload, location)


def test_patch_location_404_not_found(location):
    """
    Testing updating a location that does not exist
    """
    bad_location_id = 99999
    location_name_patch = "another test name"
    response = client.patch(
        f"/location/{bad_location_id}", json={"name": location_name_patch}
    )
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Location with ID {bad_location_id} not found."


#  ============= GET tests for locations =======================================


def test_get_locations(location):
    """
    Test retrieving locations
    """
    response = client.get("/location")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == location.id
    assert data["items"][0]["created_at"] == location.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["items"][0]["name"] == location.name
    assert data["items"][0]["notes"] == location.notes
    assert data["items"][0]["point"] == to_shape(location.point).wkt
    assert data["items"][0]["release_status"] == location.release_status
    assert data["items"][0]["elevation_accuracy"] == location.elevation_accuracy
    assert data["items"][0]["elevation_method"] == location.elevation_method
    assert data["items"][0]["coordinate_accuracy"] == location.coordinate_accuracy
    assert data["items"][0]["coordinate_method"] == location.coordinate_method
    assert data["items"][0]["state"] == location.state
    assert data["items"][0]["county"] == location.county
    assert data["items"][0]["quad_name"] == location.quad_name


def test_get_location_by_id(location):
    response = client.get(f"/location/{location.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == location.id
    assert data["created_at"] == location.created_at.isoformat().replace("+00:00", "Z")
    assert data["name"] == location.name
    assert data["point"] == to_shape(location.point).wkt
    assert data["release_status"] == location.release_status
    assert data["elevation_accuracy"] == location.elevation_accuracy
    assert data["elevation_method"] == location.elevation_method
    assert data["coordinate_accuracy"] == location.coordinate_accuracy
    assert data["coordinate_method"] == location.coordinate_method
    assert data["state"] == location.state
    assert data["county"] == location.county
    assert data["quad_name"] == location.quad_name


def test_get_sample_by_id_404_not_found(location):
    bad_location_id = 999999999
    response = client.get(f"/location/{bad_location_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Location with ID {bad_location_id} not found."


#  ============= DELETE tests for locations ====================================


def test_delete_location(second_location):
    response = client.delete(f"/location/{second_location.id}")
    assert response.status_code == 204

    # Verify the location is deleted
    response = client.get(f"/location/{second_location.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Location with ID {second_location.id} not found."


def test_delete_location_404_not_found(second_location):
    """
    Testing deleting a location that does not exist
    """
    bad_location_id = 99999
    response = client.delete(f"/location/{bad_location_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Location with ID {bad_location_id} not found."


# ============= EOF =============================================
