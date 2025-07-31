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
from datetime import datetime

from db.engine import session_ctx
from db.sample import Sample
from tests import client


#  ============= Post tests for samples =============================================
def test_add_sample(thing):
    """
    Test adding a sample to the collaborative network.
    """
    response = client.post(
        "/sample",
        json={
            "thing_id": thing.id,
            "collection_timestamp": "2025-01-01T00:00:00Z",
            "collection_method": "manual",
            "release_status": "draft",
            "sample_type": "groundwater",
            "sampler": "Test Sampler A",
        },
    )
    data = response.json()
    assert response.status_code == 201
    assert data["id"] is not None
    assert data["thing_id"] == thing.id

    # cleanup after adding the sample
    sample_id = data["id"]
    with session_ctx() as session:
        session.query(Sample).where(Sample.id == sample_id).delete()
        session.commit()


@pytest.mark.skip(reason="Geochemical sample endpoint not implemented yet")
def test_add_geochemical_sample():
    """
    Test adding a geochemical sample to the collaborative network.
    """
    response = client.post(
        "/sample/geochemical",
        json={
            "sample_id": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["sample_id"] == 1


@pytest.mark.skip(reason="Geothermal sample endpoint not implemented yet")
def test_add_geothermal_sample():
    """
    Test adding a geothermal sample to the collaborative network.
    """
    response = client.post(
        "/sample/geothermal",
        json={
            "sample_id": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["sample_id"] == 1


#  ============= Patch tests for samples =============================================
def test_patch_sample(sample):
    """
    Test updating a sample in the collaborative network.
    """
    original_method_patch = sample.collection_method
    original_timestamp_patch = sample.collection_timestamp

    collection_method_patch = "continuous"
    collection_timestamp_patch = "2025-01-02T00:00:00+00:00"
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "collection_method": collection_method_patch,
            "collection_timestamp": collection_timestamp_patch,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "id": sample.id,
        "collection_timestamp": collection_timestamp_patch.split("+")[0],
        "collection_method": collection_method_patch,
        "thing_id": sample.thing_id,
    }

    # cleanup after patching the sample
    with session_ctx() as session:
        updated_sample = session.query(Sample).filter(Sample.id == sample.id).one()
        updated_sample.collection_method = original_method_patch
        updated_sample.collection_timestamp = original_timestamp_patch
        session.commit()


def test_patch_sample_404_not_found(sample):
    """
    Test updating a sample that does not exist in the collaborative network.
    """
    collection_method_patch = "continuous"
    response = client.patch(
        "/sample/999",
        json={
            "collection_method": collection_method_patch,
        },
    )
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


def test_patch_sample_422_thing_id_not_found(sample):
    """
    Test updating a sample with a thing_id that does not exist
    """
    bad_thing_id = 999
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "thing_id": bad_thing_id,
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {
            "type": "value_error",
            "loc": ["body", "thing_id"],
            "msg": f"Value error, Thing with ID {bad_thing_id} does not exist.",
            "input": bad_thing_id,
            "ctx": {"error": {}},
        }
    ]


def test_patch_sample_422_invalid_timestamp(sample):
    """
    Test updating a sample with an invalid collection timestamp.
    """
    bad_collection_timestamp = "3500-01-01T00:00:00Z"
    bad_collection_timestamp_dt = datetime.fromisoformat(
        bad_collection_timestamp.replace("Z", "+00:00")
    )
    response = client.patch(
        f"/sample/{sample.id}",
        json={
            "collection_timestamp": bad_collection_timestamp,  # Invalid date
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == [
        {
            "type": "value_error",
            "loc": ["body", "collection_timestamp"],
            "msg": f"Value error, Collection timestamp {bad_collection_timestamp_dt} cannot be in the future.",
            "input": bad_collection_timestamp,
            "ctx": {"error": {}},
        }
    ]


#  ============= Get tests for samples =============================================
def test_get_samples(sample):
    """
    Test retrieving samples from the collaborative network.
    """
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == [
        {
            "id": sample.id,
            "collection_timestamp": sample.collection_timestamp,
            "collection_method": sample.collection_method,
            "thing_id": sample.thing_id,
        }
    ]


@pytest.mark.skip(reason="Geochemical samples endpoint not implemented yet")
def test_get_geochemical_samples():
    """
    Test retrieving geochemical samples from the collaborative network.
    """
    response = client.get("/sample/geochemical")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0


@pytest.mark.skip(reason="Geothermal samples endpoint not implemented yet")
def test_get_geothermal_samples():
    """
    Test retrieving geothermal samples from the collaborative network.
    """
    response = client.get("/sample/geothermal")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) > 0


def test_get_sample_by_id(sample):
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get(f"/sample/{sample.id}")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "id": sample.id,
        "collection_timestamp": sample.collection_timestamp,
        "collection_method": sample.collection_method,
        "thing_id": sample.thing_id,
    }


def test_get_sample_by_id_404_not_found(sample):
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get("/sample/999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


# ============= EOF =============================================
