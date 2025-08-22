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

from db.sample import Sample
from schemas.sample import ValidateSample
from tests import client, cleanup_post_test, cleanup_patch_test


# ============== Custom validators =================================================


def test_validate_sample_top_and_bottom():
    for i in range(2):
        sample_top = 10.0 if i == 0 else None
        sample_bottom = 5.0 if i == 1 else None
        with pytest.raises(
            ValidationError,
            match="Sample top and bottom must both be defined or both must be None.",
        ):
            ValidateSample(sample_top=sample_top, sample_bottom=sample_bottom)


#  ============= Post tests for samples =============================================
def test_add_sample(thing, sensor):
    """
    Test adding a sample.
    """
    payload = {
        "thing_id": thing.id,
        "sample_type": "groundwater",
        "field_sample_id": "FS-1234567",
        "sample_date": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "sampler_name": "Test Sampler",
        "qc_sample": "Duplicate",
        "sensor_id": sensor.id,
        "sample_matrix": "water",
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
    assert response.status_code == 201
    assert data["thing_id"] == payload["thing_id"]
    assert data["sample_type"] == payload["sample_type"]
    assert data["field_sample_id"] == payload["field_sample_id"]
    assert data["sample_date"] == payload["sample_date"]
    assert data["release_status"] == payload["release_status"]
    assert data["sampler_name"] == payload["sampler_name"]
    assert data["qc_sample"] == payload["qc_sample"]
    assert data["sensor_id"] == payload["sensor_id"]
    assert data["sample_matrix"] == payload["sample_matrix"]
    assert data["sample_method"] == payload["sample_method"]
    assert data["duplicate_sample_number"] == payload["duplicate_sample_number"]
    assert data["sample_top"] == payload["sample_top"]
    assert data["sample_bottom"] == payload["sample_bottom"]

    # cleanup after adding the sample
    cleanup_post_test(Sample, data["id"])


def test_409_add_sample_invalid_field_sample_id(sample, thing):
    """
    Test adding a sample with an invalid field_sample_id.
    """
    payload = {
        "thing_id": thing.id,
        "sample_type": "groundwater",
        "field_sample_id": sample.field_sample_id,  # This should already exist
        "sample_date": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "sampler_name": "Test Sampler",
        "qc_sample": "Duplicate",
        "sensor_id": None,
        "sample_matrix": "water",
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
        == f"Sample with field_sample_id {sample.field_sample_id} already exists."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"field_sample_id": sample.field_sample_id}


def test_409_add_sample_invalid_thing_id():
    """
    Test adding a sample with an invalid thing_id.
    """
    payload = {
        "thing_id": 9999999,
        "sample_type": "groundwater",
        "field_sample_id": "FS-9999999",
        "sample_date": "2025-01-01T00:00:00Z",
        "release_status": "draft",
        "sampler_name": "Test Sampler",
        "qc_sample": "Duplicate",
        "sensor_id": None,
        "sample_matrix": "water",
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
def test_patch_sample(sample):
    """
    Test updating a sample.
    """
    payload = {
        "sampler_name": "test sample b",
        "sample_method": "continuous",
        "sample_date": "2025-01-02T00:00:00Z",
    }
    response = client.patch(f"/sample/{sample.id}", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == sample.id
    assert data["sampler_name"] == payload["sampler_name"]
    assert data["sample_date"] == payload["sample_date"]
    assert data["sample_method"] == payload["sample_method"]

    # rollback after updating the sample
    cleanup_patch_test(Sample, payload, sample)


def test_patch_sample_404_not_found(sample):
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


def test_409_patch_sample_invalid_field_sample_id(sample, second_sample):
    """
    Test updating a sample with an invalid field_sample_id.
    """
    payload = {
        "field_sample_id": sample.field_sample_id,  # This should already exist
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
    assert data["detail"][0]["input"] == {"field_sample_id": sample.field_sample_id}


def test_409_patch_sample_invalid_thing_id(sample):
    """
    Test updating a sample with an invalid thing_id.
    """
    payload = {
        "thing_id": 9999999,
    }
    response = client.patch(
        f"/sample/{sample.id}",
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
def test_get_samples(sample):
    """
    Test retrieving samples
    """
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == sample.id
    assert data["items"][0]["thing_id"] == sample.thing_id
    assert data["items"][0]["sample_type"] == sample.sample_type
    assert data["items"][0]["field_sample_id"] == sample.field_sample_id
    assert data["items"][0]["sample_date"] == sample.sample_date
    assert data["items"][0]["release_status"] == sample.release_status
    assert data["items"][0]["sampler_name"] == sample.sampler_name
    assert data["items"][0]["qc_sample"] == sample.qc_sample
    assert data["items"][0]["sensor_id"] == sample.sensor_id
    assert data["items"][0]["sample_matrix"] == sample.sample_matrix
    assert data["items"][0]["sample_method"] == sample.sample_method
    assert data["items"][0]["duplicate_sample_number"] == sample.duplicate_sample_number
    assert data["items"][0]["sample_top"] == sample.sample_top
    assert data["items"][0]["sample_bottom"] == sample.sample_bottom


def test_get_sample_by_id(sample):
    """
    Test retrieving a sample by its ID.
    """
    response = client.get(f"/sample/{sample.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample.id
    assert data["thing_id"] == sample.thing_id
    assert data["sample_type"] == sample.sample_type
    assert data["field_sample_id"] == sample.field_sample_id
    assert data["sample_date"] == sample.sample_date
    assert data["release_status"] == sample.release_status
    assert data["sampler_name"] == sample.sampler_name
    assert data["qc_sample"] == sample.qc_sample
    assert data["sensor_id"] == sample.sensor_id
    assert data["sample_matrix"] == sample.sample_matrix
    assert data["sample_method"] == sample.sample_method
    assert data["duplicate_sample_number"] == sample.duplicate_sample_number
    assert data["sample_top"] == sample.sample_top
    assert data["sample_bottom"] == sample.sample_bottom


def test_get_sample_by_id_404_not_found(sample):
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
