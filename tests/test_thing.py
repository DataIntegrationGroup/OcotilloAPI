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
from tests import client, override_authentication
from main import app
from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# POST tests ===================================================================


def test_add_well(location):
    # response = client.post(
    #     "/lexicon/add", json={"term": "Monitoring", "definition": "Monitoring Well"}
    # )
    # assert response.status_code == 200
    # response = client.post(
    #     "/lexicon/add", json={"term": "Production", "definition": "Production Well"}
    # )
    # assert response.status_code == 200

    response = client.post(
        "/thing",
        json={
            "thing_type": "water well",
            "location_id": location.id,
            "name": "Test Well",
            "api_id": "1001-0001",
            "ose_pod_id": "RA-0001",
            "well_type": "Monitoring",
            "well_depth": 100.0,
            "well_construction_notes": "this is a test of notes",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Well"
    assert data["well_type"] == "Monitoring"

    response = client.post(
        "/thing",
        json={
            "thing_type": "water well",
            "location_id": location.id,
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
        "/thing",
        json={
            "location_id": 1,
            "name": "Test Spring",
            "thing_type": "spring",
            "spring_type": "Ephemeral",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data

    assert "name" in data
    assert data["name"] == "Test Spring"

    assert "thing_type" in data
    assert data["thing_type"] == "spring"

    assert "spring_type" in data
    assert data["spring_type"] == "Ephemeral"


def test_add_well_screen():
    # response = client.post(
    #     "/lexicon/add",
    #     json={"term": "PVC", "definition": "PVC Well Screen"},
    # )
    # assert response.status_code == 200
    response = client.post(
        "/thing/well-screen",
        json={
            "thing_id": 1,
            "screen_depth_top": 10.0,
            "screen_depth_bottom": 20.0,
            "screen_type": "PVC",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["thing_id"] == 1


def test_add_thing_link():
    response = client.post(
        "/thing/id-link",
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


# GET tests ====================================================================


def test_get_water_wells(water_well_thing):
    response = client.get("/thing/water-well")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == water_well_thing.id
    assert data["items"][0][
        "created_at"
    ] == water_well_thing.created_at.isoformat().replace("+00:00", "Z")
    assert data["items"][0]["name"] == water_well_thing.name
    assert data["items"][0]["thing_type"] == water_well_thing.thing_type
    assert data["items"][0]["release_status"] == water_well_thing.release_status
    assert data["items"][0]["well_type"] == water_well_thing.well_type
    assert data["items"][0]["well_depth"] == water_well_thing.well_depth
    assert data["items"][0]["hole_depth"] == water_well_thing.hole_depth
    assert (
        data["items"][0]["well_construction_notes"]
        == water_well_thing.well_construction_notes
    )


def test_get_water_well_by_id(water_well_thing):
    response = client.get(f"/thing/water-well/{water_well_thing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == water_well_thing.id
    assert data["created_at"] == water_well_thing.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["name"] == water_well_thing.name
    assert data["thing_type"] == water_well_thing.thing_type
    assert data["release_status"] == water_well_thing.release_status
    assert data["well_type"] == water_well_thing.well_type
    assert data["well_depth"] == water_well_thing.well_depth
    assert data["hole_depth"] == water_well_thing.hole_depth
    assert data["well_construction_notes"] == water_well_thing.well_construction_notes


def test_get_water_well_by_id_404_not_found(water_well_thing):
    bad_id = 99999
    response = client.get(f"/thing/water-well/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_get_water_well_by_id_404_wrong_type(spring_thing):
    response = client.get(f"/thing/water-well/{spring_thing.id}")
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {spring_thing.id} is not a water well Thing. It is a spring Thing."
    )
    assert data["detail"][0]["loc"] == ["path", "thing_id"]
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": spring_thing.id}


def test_get_springs(spring_thing):
    response = client.get("/thing/spring")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == spring_thing.id
    assert data["items"][0][
        "created_at"
    ] == spring_thing.created_at.isoformat().replace("+00:00", "Z")
    assert data["items"][0]["name"] == spring_thing.name
    assert data["items"][0]["thing_type"] == spring_thing.thing_type
    assert data["items"][0]["release_status"] == spring_thing.release_status
    assert data["items"][0]["spring_type"] == spring_thing.spring_type


def test_get_spring_by_id(spring_thing):
    response = client.get(f"/thing/spring/{spring_thing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == spring_thing.id
    assert data["created_at"] == spring_thing.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["name"] == spring_thing.name
    assert data["thing_type"] == spring_thing.thing_type
    assert data["release_status"] == spring_thing.release_status
    assert data["spring_type"] == spring_thing.spring_type


def test_get_spring_by_id_404_not_found(spring_thing):
    bad_id = 99999
    response = client.get(f"/thing/spring/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_get_spring_by_id_404_wrong_type(water_well_thing):
    response = client.get(f"/thing/spring/{water_well_thing.id}")
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {water_well_thing.id} is not a spring Thing. It is a water well Thing."
    )
    assert data["detail"][0]["loc"] == ["path", "thing_id"]
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": water_well_thing.id}


# def test_get_well_by_id():
#     response = client.get("/thing/well/1")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["id"] == 1


def test_get_well_screens():
    # TODO: improve test indepedence
    response = client.get("/thing/well-screen")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_thing_links():
    # TODO: improve test indepedence
    response = client.get("/thing/id-link")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_thing_links_by_id():
    # TODO: improve test indepedence
    response = client.get("/thing/id-link/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["thing_id"] == 1
    assert data["relation"] == "same_as"
    assert data["alternate_id"] == "4321-1234"
    assert data["alternate_organization"] == "USGS"


def test_get_thing_links_by_thing_id():
    # TODO: improve test indepedence
    response = client.get("/thing/1/id-link")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    data = data["items"]
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["id"] == 1
    assert item["thing_id"] == 1
    assert item["relation"] == "same_as"
    assert item["alternate_id"] == "4321-1234"
    assert item["alternate_organization"] == "USGS"


def test_item_get_well_filter():
    response = client.get("/thing", params={"query": "well_type eq 'Monitoring'"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    # assert "api_id" in data["items"][0]
    # assert data["items"][0]["api_id"] == "1001-0002"


# @pytest.mark.skip
def test_item_get_well_filter_nonexistent():
    # response = client.get("/thing/well", params={"well_type": "9999-9999"})
    response = client.get("/thing", params={"query": "well_type eq 'foo'"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 0


# @pytest.mark.skip
def test_item_get_well_screens():
    response = client.get("/thing/well-screen/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["thing_id"] == 1
    assert data["screen_depth_top"] == 10.0
    assert data["screen_depth_bottom"] == 20.0


# weaver tests
def test_weaver_get_wells_geojson():
    response = client.get("/geospatial", params={"type": "well"})
    assert response.status_code == 200
    data = response.json()
    assert "type" in data
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert "id" in data["features"][0]["properties"]


def test_weaver_get_all_collabnet_wells():
    response = client.get(
        "/geospatial", params={"type": "well", "group": "collabnet"}
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
    assert isinstance(data, dict)
    assert "items" in data
    assert len(data["items"]) > 0
    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert "addresses" in item
    assert "emails" in item
    assert "phones" in item

    assert isinstance(item["addresses"], list)
    assert isinstance(item["emails"], list)
    assert isinstance(item["phones"], list)


# Patch tests
def test_patch_thing_link():
    response = client.patch(
        "/thing/id-link/1",
        json={
            "relation": "same_as",
            "alternate_id": "USGS-43211234",
            "alternate_organization": "USGS",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["relation"] == "same_as"
    assert data["alternate_id"] == "USGS-43211234"
    assert data["alternate_organization"] == "USGS"


def test_patch_thing():
    response = client.patch(
        "/thing/1",
        json={
            "name": "Updated Test Thing",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Updated Test Thing"


def test_patch_well():
    response = client.patch(
        "/thing/1",
        json={
            "well_depth": 150.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["well_depth"] == 150.0


def test_patch_thing_location():
    response = client.patch(
        "/thing/4/location",
        json={
            "point": "POINT(-106.61 35.08)",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["point"] == "POINT (-106.61 35.08)"


# ============= EOF =============================================
