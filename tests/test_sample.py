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
            "release_status": "draft",
        },
    )
    data = response.json()
    assert response.status_code == 201
    assert data["id"] is not None
    assert data["thing_id"] == 1


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


#  ============= Get tests for samples =============================================
def test_get_samples():
    """
    Test retrieving samples from the collaborative network.
    """
    response = client.get("/sample")
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert len(data['items']) > 0

def test_get_geochemical_samples():
    """
    Test retrieving geochemical samples from the collaborative network.
    """
    response = client.get("/sample/geochemical")
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert len(data['items']) > 0


def test_get_geothermal_samples():
    """
    Test retrieving geothermal samples from the collaborative network.
    """
    response = client.get("/sample/geothermal")
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert len(data['items']) > 0


def test_get_sample_by_id():
    """
    Test retrieving a sample from the collaborative network.
    """
    response = client.get("/sample/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1


# ============= EOF =============================================
