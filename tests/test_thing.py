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

from tests import client

def test_add_group():
    response = client.post(
        "/group",
        json={
            "name": "collabnet",
            "description": "CollabNet Group for testing",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "collabnet"


def test_add_well():
    # response = client.post(
    #     "/lexicon/add", json={"term": "Monitoring", "definition": "Monitoring Well"}
    # )
    # assert response.status_code == 200
    # response = client.post(
    #     "/lexicon/add", json={"term": "Production", "definition": "Production Well"}
    # )
    # assert response.status_code == 200

    response = client.post(
        "/thing/well",
        json={
            "location_id": 1,
            "name": "Test Well",
            "api_id": "1001-0001",
            "ose_pod_id": "RA-0001",
            "well_type": "Monitoring",
            "well_depth": 100.0,
            "construction_notes": "this is a test of notes",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data

    response = client.post(
        "/thing/well",
        json={
            "location_id": 2,
            "name": "Test Well 2",
            "api_id": "1001-0002",
            "ose_pod_id": "RA-0002",
            "well_type": "Production",
            "well_depth": 1200.0,
            "group": "collabnet",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_add_spring():
    response = client.post(
        "/thing/spring",
        json={
            "location_id": 1,
            "name": "Test Spring",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data


def test_add_well_screen():
    # response = client.post(
    #     "/lexicon/add",
    #     json={"term": "PVC", "definition": "PVC Well Screen"},
    # )
    # assert response.status_code == 200
    response = client.post(
        "/thing/well/screen",
        json={
            "well_id": 1,
            "screen_depth_top": 10.0,
            "screen_depth_bottom": 20.0,
            "screen_type": "PVC",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["well_id"] == 1


def test_add_thing_link():
    response = client.post(
        "/thing/link",
        json={
            "thing_id": 1,
            "relation": "same_as",
            "alternate_id": "4321-1234",
            "alternate_organization": "USGS",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["thing_id"] == 1
    assert data["alternate_id"] == "4321-1234"


# ===================== get ==========================
def test_get_wells():
    response = client.get("/thing/well")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_springs():
    response = client.get("/thing/spring")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_well_by_id():
    response = client.get("/thing/well/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1


def test_get_well_screens():
    response = client.get("/thing/well/screen")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_item_get_well_filter():
    response = client.get("/thing/well", params={"query": "well_type eq 'Monitoring'"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    # assert "api_id" in data["items"][0]
    # assert data["items"][0]["api_id"] == "1001-0002"


# @pytest.mark.skip
def test_item_get_well_filter_nonexistent():
    # response = client.get("/thing/well", params={"well_type": "9999-9999"})
    response = client.get("/thing/well", params={"query": "well_type eq 'foo'"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 0


def test_item_get_wells():
    response = client.get("/thing/well/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    # assert data["location_id"] == 1


def test_item_get_spring():
    response = client.get("/thing/spring/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    # assert data["location_id"] == 1


# @pytest.mark.skip
def test_item_get_well_screens():
    response = client.get("/thing/well/screen/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["well_id"] == 1
    assert data["screen_depth_top"] == 10.0
    assert data["screen_depth_bottom"] == 20.0


# weaver tests
def test_weaver_get_wells_geojson():
    response = client.get("/thing", params={"type": "well", "format": "geojson"})
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert 'id' in data["features"][0]["properties"]


def test_weaver_get_all_collabnet_wells():
    response = client.get(
        "/thing",
        params={"type": "well", "group": "collabnet", "format": "geojson"}
    )  # TODO: QUESTION: use type filter and a group filter instead of /collabnet endpoint?
    assert response.status_code == 200
    data = response.json()

    assert "features" in data
    assert len(data["features"]) > 0
    for feature in data["features"]:
        assert "geometry" in feature
        assert isinstance(feature["geometry"], dict)
        assert "properties" in feature
        assert isinstance(feature["properties"], dict)
        assert "coordinates" in feature["geometry"]
        assert "id" in feature or "name" in feature["properties"]
        assert "group" in feature["properties"]


def test_weaver_thing_contact_info_by_id():
    response = client.get("/contact?thing_id=1")  # or something like this
    assert response.status_code == 200
    data = response.json()
    assert isinstance(
        data, dict
    )
    assert 'items' in data
    assert len(data['items']) > 0
    item = data['items'][0]
    assert 'id' in item
    assert 'name' in item
    assert 'addresses' in item
    assert 'emails' in item
    assert 'phones' in item

    assert isinstance(item['addresses'], list)
    assert isinstance(item['emails'], list)
    assert isinstance(item['phones'], list)



# ============= EOF =============================================
