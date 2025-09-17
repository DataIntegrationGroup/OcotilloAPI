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
import pytest
from pydantic import ValidationError

from main import app
from core.dependencies import admin_function, editor_function, viewer_function
from db.sample import Sample
from schemas.sample import ValidateSample
from tests import client, cleanup_post_test, cleanup_patch_test, override_authentication


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


# ============== Custom validators =================================================


def test_validate_sample_top_and_bottom():
    for i in range(2):
        depth_top = 10.0 if i == 0 else None
        depth_bottom = 5.0 if i == 1 else None
        with pytest.raises(
            ValidationError,
            match="Depth top and bottom must both be defined or both must be None.",
        ):
            ValidateSample(depth_top=depth_top, depth_bottom=depth_bottom)


#  ============= Post tests for samples =============================================
def test_add_sample(groundwater_level_field_activity, sensor):
    """
    Test adding a sample.
    """
    payload = {
        "field_activity_id": groundwater_level_field_activity.id,
        "sensor_id": sensor.id,
        "sample_date": "2025-01-01T14:00:00Z",
        "sample_name": "second groundwater level field activity name",
        "sample_matrix": "water",
        "sample_method": "grab sample",
        "sampler_name": "Ptolemy I Soter",
        "qc_type": "Normal",
        "depth_top": None,
        "depth_bottom": None,
    }
    response = client.post(
        "/sample",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert "created_at" in data
    assert data["field_activity_id"] == payload["field_activity_id"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["sample_date"] == payload["sample_date"]
    assert data["sample_name"] == payload["sample_name"]
    assert data["sample_matrix"] == payload["sample_matrix"]
    assert data["sample_method"] == payload["sample_method"]
    assert data["sampler_name"] == payload["sampler_name"]
    assert data["qc_type"] == payload["qc_type"]
    assert data["depth_top"] == payload["depth_top"]
    assert data["depth_bottom"] == payload["depth_bottom"]

    # cleanup after adding the sample
    cleanup_post_test(Sample, data["id"])


def test_409_add_sample_invalid_field_sample_id(water_chemistry_sample, spring_thing):
    """
    Test adding a sample with an invalid field_sample_id.
    """
    payload = {
        "thing_id": spring_thing.id,
        "activity_type": "water chemistry",
        "field_sample_id": water_chemistry_sample.field_sample_id,  # This should already exist
        "sample_date": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "sampler_name": "Test Sampler",
        "qc_sample": "Duplicate",
        "sensor_id": None,
        "sample_matrix": "groundwater",
        "sample_method": "manual",
        "duplicate_sample_number": 3,
        "sample_top": 2,
        "sample_bottom": 3,
    }
    response = client.post(
        "/sample",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 409
    assert data["detail"][0]["loc"] == ["body", "field_sample_id"]
    assert (
        data["detail"][0]["msg"]
        == f"Sample with field_sample_id {water_chemistry_sample.field_sample_id} already exists."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "field_sample_id": water_chemistry_sample.field_sample_id
    }


def test_409_add_sample_invalid_thing_id():
    """
    Test adding a sample with an invalid thing_id.
    """
    payload = {
        "thing_id": 9999999,
        "activity_type": "water chemistry",
        "field_sample_id": "FS-9999999",
        "sample_date": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "sampler_name": "Test Sampler",
        "qc_sample": "Duplicate",
        "sensor_id": None,
        "sample_matrix": "groundwater",
        "sample_method": "manual",
        "duplicate_sample_number": 3,
        "sample_top": 2,
        "sample_bottom": 3,
    }
    response = client.post(
        "/sample",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 409
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {payload['thing_id']} does not exist."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": payload["thing_id"]}


#  ============= Patch tests for samples =============================================
def test_patch_sample(water_chemistry_sample):
    """
    Test updating a sample.
    """
    payload = {
        "sampler_name": "test sample b",
        "sample_method": "continuous",
        "sample_date": "2025-01-02T00:00:00Z",
        "release_status": "private",
    }
    response = client.patch(f"/sample/{water_chemistry_sample.id}", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == water_chemistry_sample.id
    assert data["sampler_name"] == payload["sampler_name"]
    assert data["sample_date"] == payload["sample_date"]
    assert data["sample_method"] == payload["sample_method"]
    assert data["release_status"] == payload["release_status"]

    # rollback after updating the sample
    cleanup_patch_test(Sample, payload, water_chemistry_sample)


def test_patch_sample_404_not_found(water_chemistry_sample):
    """
    Test updating a sample that does not exist
    """
    sample_method_patch = "continuous"
    response = client.patch(
        "/sample/999",
        json={
            "sample_method": sample_method_patch,
        },
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


def test_409_patch_sample_invalid_field_sample_id(
    water_chemistry_sample, second_sample
):
    """
    Test updating a sample with an invalid field_sample_id.
    """
    payload = {
        "field_sample_id": water_chemistry_sample.field_sample_id,  # This should already exist
    }
    response = client.patch(
        f"/sample/{second_sample.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 409
    assert data["detail"][0]["loc"] == ["body", "field_sample_id"]
    assert (
        data["detail"][0]["msg"]
        == f"Sample with field_sample_id {payload['field_sample_id']} already exists."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {
        "field_sample_id": water_chemistry_sample.field_sample_id
    }


def test_409_patch_sample_invalid_thing_id(water_chemistry_sample):
    """
    Test updating a sample with an invalid thing_id.
    """
    payload = {
        "thing_id": 9999999,
    }
    response = client.patch(
        f"/sample/{water_chemistry_sample.id}",
        json=payload,
    )
    data = response.json()
    assert response.status_code == 409
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {payload['thing_id']} does not exist."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": payload["thing_id"]}


#  ============= Get tests for samples =============================================
def test_get_samples(
    water_chemistry_sample, groundwater_level_sample, geothermal_sample
):
    """
    Test retrieving samples
    """
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3

    for item in data["items"]:
        assert "id" in item
        assert "created_at" in item
        assert "thing" in item
        assert "activity_type" in item
        assert "field_sample_id" in item
        assert "sample_date" in item
        assert "release_status" in item
        assert "sampler_name" in item
        assert "qc_sample" in item
        assert "sensor_id" in item
        assert "sample_matrix" in item
        assert "sample_method" in item
        assert "duplicate_sample_number" in item
        assert "sample_top" in item
        assert "sample_bottom" in item


def test_get_sample_by_id(water_chemistry_sample, water_well_thing):
    """
    Test retrieving a sample by its ID.
    """
    response = client.get(f"/sample/{water_chemistry_sample.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == water_chemistry_sample.id
    assert data["created_at"] == water_chemistry_sample.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["thing"]["id"] == water_well_thing.id
    assert data["activity_type"] == water_chemistry_sample.activity_type
    assert data["field_sample_id"] == water_chemistry_sample.field_sample_id
    assert data["sample_date"] == water_chemistry_sample.sample_date
    assert data["release_status"] == water_chemistry_sample.release_status
    assert data["sampler_name"] == water_chemistry_sample.sampler_name
    assert data["qc_sample"] == water_chemistry_sample.qc_sample
    assert data["sensor_id"] == water_chemistry_sample.sensor_id
    assert data["sample_matrix"] == water_chemistry_sample.sample_matrix
    assert data["sample_method"] == water_chemistry_sample.sample_method
    assert (
        data["duplicate_sample_number"]
        == water_chemistry_sample.duplicate_sample_number
    )
    assert data["sample_top"] == water_chemistry_sample.sample_top
    assert data["sample_bottom"] == water_chemistry_sample.sample_bottom


def test_get_sample_by_id_404_not_found(water_chemistry_sample):
    """
    Test retrieving a sample that does not exist.
    """
    response = client.get("/sample/999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


# DELETE tests =================================================================


def test_delete_sample(second_sample):
    response = client.delete(f"/sample/{second_sample.id}")
    assert response.status_code == 204

    # verify the sample is deleted
    response = client.get(f"/sample/{second_sample.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sample with ID {second_sample.id} not found."


def test_delete_sample_404_not_found(second_sample):
    bad_sample_id = 999999
    response = client.delete(f"/sample/{bad_sample_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Sample with ID {bad_sample_id} not found."


# ============= EOF =============================================
