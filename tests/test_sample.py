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

from db.engine import session_ctx
from db.sample import Sample
from schemas_v2.sample import ValidateSample
from tests import client

# ============= module & function fixtures =======================================


@pytest.fixture(scope="function")
def second_sample(thing, sensor):
    with session_ctx() as session:
        sample = Sample(
            thing_id=thing.id,
            sample_type="groundwater",
            field_sample_id="FS-9999999",
            sample_date="2025-01-01T00:00:00Z",
            release_status="draft",
            sampler_name="Test Sampler",
            qc_sample="Duplicate",
            sensor_id=sensor.id,
            sample_matrix="water",
            sample_method="manual",
            duplicate_sample_number=3,
            sample_top=2,
            sample_bottom=3,
        )
        session.add(sample)
        session.commit()
        yield sample
        session.delete(sample)
        session.commit()


# ============== Custom validators =================================================


def test_validate_sample_top_and_bottom():
    for i in range(2):
        sample_top = 10.0 if i == 0 else None
        sample_bottom = 5.0 if i == 1 else None
        try:
            invalid_sample = ValidateSample(
                sample_top=sample_top, sample_bottom=sample_bottom
            )
        except ValueError as e:
            assert (
                str(e)
                == "Sample top and bottom must both be defined or both must be None."
            )


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
    with session_ctx() as session:
        session.delete(session.get(Sample, data["id"]))
        session.commit()


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
    assert (
        data["detail"]
        == f"Sample with field_sample_id {sample.field_sample_id} already exists."
    )


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
    assert data["detail"] == f"Thing with ID {payload['thing_id']} does not exist."


#  ============= Patch tests for samples =============================================
def test_patch_sample(sample):
    """
    Test updating a sample.
    """
    new_sampler_name = "Test Sampler B"
    new_sample_method = "continuous"
    new_sample_date = "2025-01-02T00:00:00Z"
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "sampler_name": new_sampler_name,
            "sample_method": new_sample_method,
            "sample_date": new_sample_date,
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == sample.id
    assert data["sampler_name"] == new_sampler_name
    assert data["sample_date"] == new_sample_date
    assert data["sample_method"] == new_sample_method

    # rollback after updating the sample
    with session_ctx() as session:
        updated_sample = session.get(Sample, sample.id)
        updated_sample.sampler_name = sample.sampler_name
        updated_sample.sample_method = sample.sample_method
        updated_sample.sample_date = sample.sample_date
        session.commit()


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
    assert (
        data["detail"]
        == f"Sample with field_sample_id {payload['field_sample_id']} already exists."
    )


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
    assert data["detail"] == f"Thing with ID {payload['thing_id']} does not exist."


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


# ============= EOF =============================================
