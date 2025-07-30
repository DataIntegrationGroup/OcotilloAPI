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

from tests import client, thing  # noqa: F401


import pytest
from db.engine import session_ctx
from db.sample import Sample


@pytest.fixture
def sample_fixture(thing):
    with session_ctx() as session:
        sample = Sample(
            thing_id=thing.id,
            collection_timestamp="2025-01-01T00:00:00+00:00",
            collection_method="manual",
        )
        session.add(sample)
        session.commit()
        session.refresh(sample)
        yield thing, sample
        session.delete(sample)
        session.commit()


#  ============= Post tests for samples =============================================
def test_add_sample():
    """
    Test adding a sample to the collaborative network.
    """
    response = client.post(
        "/sample",
        json={
            "thing_id": 1,
            "collection_timestamp": "2025-01-01T00:00:00Z",
            "collection_method": "manual",
        },
    )
    data = response.json()
    assert response.status_code == 201
    assert data["id"] is not None
    assert data["thing_id"] == 1


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
def test_patch_sample(sample_fixture):
    """
    Test updating a sample in the collaborative network.
    """
    thing, sample = sample_fixture
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
        "thing_id": thing.id,
    }


def test_patch_sample_404_not_found(sample_fixture):
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


#  ============= Get tests for samples =============================================
def test_get_samples(sample_fixture):
    """
    Test retrieving samples from the collaborative network.
    """
    thing, sample = sample_fixture
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == [
        {
            "id": sample.id,
            "collection_timestamp": sample.collection_timestamp.isoformat(),
            "collection_method": sample.collection_method,
            "thing_id": thing.id,
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


def test_get_sample_by_id_200(sample_fixture):
    """
    Test retrieving a sample from the collaborative network.
    """
    thing, sample = sample_fixture
    response = client.get("/sample/1")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "id": sample.id,
        "collection_timestamp": sample.collection_timestamp.isoformat(),
        "collection_method": sample.collection_method,
        "thing_id": thing.id,
    }


def test_get_sample_by_id_404_not_found(sample_fixture):
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get("/sample/999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Sample with ID 999 not found."


# ============= EOF =============================================
