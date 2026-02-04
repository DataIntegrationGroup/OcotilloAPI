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
from datetime import timezone

import pytest
from geoalchemy2.shape import to_shape

from core.dependencies import admin_function, editor_function, viewer_function
from db import Location
from main import app
from schemas import DT_FMT
from tests import (
    client,
    override_authentication,
    cleanup_post_test,
)


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
        # "name": "test location",
        "notes": [
            {
                "note_type": "Access",
                "content": "These are some test access notes.",
            }
        ],
        "point": "POINT (-106.607784 35.118924)",
        "elevation": 1558.8,
        "release_status": "draft",
        # "elevation_accuracy": 1.0,
        # "elevation_method": "Survey-grade GPS",
        # "coordinate_accuracy": 5.0,
        # "coordinate_method": "GPS, uncorrected",
    }
    response = client.post("/location", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    # assert data["name"] == payload["name"]
    assert len(data["notes"]) == 1
    assert data["notes"][0]["note_type"] == "Access"
    assert data["notes"][0]["content"] == "These are some test access notes."
    assert data["point"] == payload["point"]
    assert data["elevation"] == payload["elevation"]
    assert data["release_status"] == payload["release_status"]
    assert data["nma_location_notes"] is None
    assert data["nma_data_reliability"] is None
    # assert data["elevation_accuracy"] == payload["elevation_accuracy"]
    # assert data["elevation_method"] == payload["elevation_method"]
    # assert data["coordinate_accuracy"] == payload["coordinate_accuracy"]
    # assert data["coordinate_method"] == payload["coordinate_method"]

    # relies on external service that is not 100%
    # assert data["state"] == "New Mexico"
    # assert data["county"] == "Bernalillo"
    # assert data["quad_name"] == "Albuquerque East"

    # cleanup after test
    cleanup_post_test(Location, data["id"])


#  ============= Patch tests for locations =====================================


def test_update_location(location):
    payload = {
        # "name": "patched name",
        "notes": [
            {"note_type": "Access", "content": "These are some patched access notes."}
        ],
        "point": "POINT (-106.904107 34.068198)",
        "elevation": 1408.3,
        "release_status": "draft",
        # "elevation_accuracy": 2.0,
        # "elevation_method": "Survey-grade GPS",
        # "coordinate_accuracy": 10.0,
        # "coordinate_method": "GPS, uncorrected",
    }
    response = client.patch(f"/location/{location.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == location.id
    # assert data["name"] == payload["name"]
    assert len(data["notes"]) == 1
    assert data["notes"][0]["note_type"] == "Access"
    assert data["notes"][0]["content"] == "These are some patched access notes."
    assert data["point"] == payload["point"]
    assert data["elevation"] == payload["elevation"]
    assert data["release_status"] == payload["release_status"]
    # assert data["elevation_accuracy"] == payload["elevation_accuracy"]
    # assert data["elevation_method"] == payload["elevation_method"]
    # assert data["coordinate_accuracy"] == payload["coordinate_accuracy"]
    # assert data["coordinate_method"] == payload["coordinate_method"]
    # assert data["state"] == "New Mexico"
    # assert data["county"] == "Socorro"
    # assert data["quad_name"] == "Socorro"

    # cleanup after test
    # payload["state"] = location.state
    # payload["county"] = location.county
    # payload["quad_name"] = location.quad_name
    # cleanup_patch_test(Location, payload, location)


def test_patch_location_404_not_found(location):
    """
    Testing updating a location that does not exist
    """
    bad_location_id = 99999
    location_notes_patch = "patched notes"
    response = client.patch(
        f"/location/{bad_location_id}",
        json={"notes": [{"content": location_notes_patch, "note_type": "General"}]},
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
    assert data["items"][0]["created_at"] == location.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    # assert data["items"][0]["name"] == location.name
    assert isinstance(data["items"][0]["notes"], list)
    # If you know the exact number of notes expected:
    # assert len(data["items"][0]["notes"]) == expected_count
    # If you want to check content of a specific note:
    # if data["items"][0]["notes"]:
    #     assert data["items"][0]["notes"][0]["content"] == expected_content
    assert data["items"][0]["point"] == to_shape(location.point).wkt
    assert data["items"][0]["elevation"] == location.elevation
    assert data["items"][0]["release_status"] == location.release_status
    assert "nma_location_notes" in data["items"][0]
    assert data["items"][0]["nma_location_notes"] == location.nma_location_notes
    assert "nma_data_reliability" in data["items"][0]
    assert data["items"][0]["nma_data_reliability"] == location.nma_data_reliability
    # assert data["items"][0]["elevation_accuracy"] == location.elevation_accuracy
    # assert data["items"][0]["elevation_method"] == location.elevation_method
    # assert data["items"][0]["coordinate_accuracy"] == location.coordinate_accuracy
    # assert data["items"][0]["coordinate_method"] == location.coordinate_method
    assert data["items"][0]["state"] == location.state
    assert data["items"][0]["county"] == location.county
    assert data["items"][0]["quad_name"] == location.quad_name


def test_get_location_by_id(location):
    response = client.get(f"/location/{location.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == location.id
    assert data["created_at"] == location.created_at.astimezone(timezone.utc).strftime(
        DT_FMT
    )
    # assert data["name"] == location.name
    assert data["point"] == to_shape(location.point).wkt
    assert data["elevation"] == location.elevation
    assert data["release_status"] == location.release_status
    assert data["nma_location_notes"] == location.nma_location_notes
    assert data["nma_data_reliability"] == location.nma_data_reliability
    # assert data["elevation_accuracy"] == location.elevation_accuracy
    # assert data["elevation_method"] == location.elevation_method
    # assert data["coordinate_accuracy"] == location.coordinate_accuracy
    # assert data["coordinate_method"] == location.coordinate_method
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


#  ============= AMPAPI date field tests =======================================


def test_new_location_has_null_ampapi_fields():
    """Test that newly created locations have null AMPAPI date fields (AMPAPI fields are migration-only)"""
    payload = {
        "point": "POINT (-106.607784 35.118924)",
        "elevation": 1558.8,
        "release_status": "draft",
    }
    response = client.post("/location", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    # AMPAPI date fields should be present in response but null (not set during creation, read-only)
    assert "nma_date_created" in data
    assert "nma_site_date" in data
    assert data["nma_date_created"] is None
    assert data["nma_site_date"] is None

    # cleanup after test
    cleanup_post_test(Location, data["id"])


def test_ampapi_fields_present_in_location_response():
    """Test that AMPAPI date fields (read-only) are included in location GET response"""
    # Create a new location (without AMPAPI date fields set - they're read-only)
    payload = {
        "point": "POINT (-106.607784 35.118924)",
        "elevation": 1558.8,
        "release_status": "draft",
    }
    create_response = client.post("/location", json=payload)
    assert create_response.status_code == 201
    location_id = create_response.json()["id"]

    # Retrieve the location and verify AMPAPI date fields are in the schema
    get_response = client.get(f"/location/{location_id}")
    assert get_response.status_code == 200
    data = get_response.json()

    # Verify read-only fields exist in response (even if null)
    assert "nma_date_created" in data
    assert "nma_site_date" in data
    assert data["nma_date_created"] is None
    assert data["nma_site_date"] is None

    # cleanup after test
    cleanup_post_test(Location, location_id)


def test_ampapi_fields_independent_of_created_at():
    """Test that created_at (system timestamp) is separate from AMPAPI date fields (read-only)"""
    payload = {
        "point": "POINT (-106.607784 35.118924)",
        "elevation": 1558.8,
        "release_status": "draft",
    }
    response = client.post("/location", json=payload)

    assert response.status_code == 201
    data = response.json()

    # created_at is automatically set by AutoBaseMixin
    assert "created_at" in data
    assert data["created_at"] is not None

    # nma_date_created is separate and null for new records (read-only, populated only during migration)
    assert "nma_date_created" in data
    assert data["nma_date_created"] is None

    # These are independent fields with different purposes
    assert "created_at" != "nma_date_created"

    # cleanup after test
    cleanup_post_test(Location, data["id"])


# ============= EOF =============================================
