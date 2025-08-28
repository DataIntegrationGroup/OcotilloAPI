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

from db import Thing, WellScreen, ThingIdLink
from tests import client, override_authentication, cleanup_post_test, cleanup_patch_test
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


def test_add_water_well(location, group):
    payload = {
        "location_id": location.id,
        "group_id": group.id,
        "release_status": "draft",
        "name": "Test Well",
        "well_type": "Monitoring",
        "well_depth": 100.0,
        "hole_depth": 110,
        "well_construction_notes": "this is a test of notes",
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
    assert data["name"] == payload["name"]
    assert data["thing_type"] == "water well"
    assert data["well_type"] == payload["well_type"]
    assert data["hole_depth"] == payload["hole_depth"]
    assert data["well_depth"] == payload["well_depth"]
    assert data["well_construction_notes"] == payload["well_construction_notes"]

    cleanup_post_test(Thing, data["id"])


def test_add_water_well_409_bad_group_id(location):
    bad_group_id = 9999
    payload = {
        "location_id": location.id,
        "group_id": bad_group_id,  # Invalid group ID
        "release_status": "draft",
        "name": "Test Well",
        "well_type": "Monitoring",
        "well_depth": 100.0,
        "hole_depth": 110,
        "well_construction_notes": "this is a test of notes",
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "group_id"]
    assert data["detail"][0]["msg"] == f"Group with ID {bad_group_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"group_id": bad_group_id}


def test_add_water_well_409_bad_location_id(group):
    bad_location_id = 9999
    payload = {
        "location_id": bad_location_id,
        "group_id": group.id,  # Invalid group ID
        "release_status": "draft",
        "name": "Test Well",
        "well_type": "Monitoring",
        "well_depth": 100.0,
        "hole_depth": 110,
        "well_construction_notes": "this is a test of notes",
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "location_id"]
    assert data["detail"][0]["msg"] == f"Location with ID {bad_location_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"location_id": bad_location_id}


def test_add_spring(location, group):
    payload = {
        "location_id": location.id,
        "group_id": group.id,
        "name": "test spring",
        "release_status": "draft",
        "spring_type": "Ephemeral",
    }
    response = client.post("/thing/spring", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["name"] == payload["name"]
    assert data["release_status"] == payload["release_status"]
    assert data["spring_type"] == payload["spring_type"]

    cleanup_post_test(Thing, data["id"])


def test_add_spring_409_bad_group_id(location):
    bad_group_id = 9999
    payload = {
        "location_id": location.id,
        "group_id": bad_group_id,  # Invalid group ID
        "name": "test spring",
        "release_status": "draft",
        "spring_type": "Ephemeral",
    }
    response = client.post("/thing/spring", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "group_id"]
    assert data["detail"][0]["msg"] == f"Group with ID {bad_group_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"group_id": bad_group_id}


def test_add_spring_409_bad_location_id(group):
    bad_location_id = 9999
    payload = {
        "location_id": bad_location_id,
        "group_id": group.id,  # Invalid group ID
        "name": "test spring",
        "release_status": "draft",
        "spring_type": "Ephemeral",
    }
    response = client.post("/thing/spring", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "location_id"]
    assert data["detail"][0]["msg"] == f"Location with ID {bad_location_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"location_id": bad_location_id}


def test_add_well_screen(water_well_thing):
    payload = {
        "thing_id": water_well_thing.id,
        "screen_depth_top": 10.0,
        "screen_depth_bottom": 20.0,
        "screen_type": "PVC",
    }
    response = client.post("/thing/well-screen", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["thing_id"] == water_well_thing.id
    assert data["screen_depth_top"] == payload["screen_depth_top"]
    assert data["screen_depth_bottom"] == payload["screen_depth_bottom"]
    assert data["screen_type"] == payload["screen_type"]

    cleanup_post_test(WellScreen, data["id"])


def test_add_well_screen_409_bad_thing_id():
    bad_thing_id = 9999
    payload = {
        "thing_id": bad_thing_id,
        "screen_depth_top": 10.0,
        "screen_depth_bottom": 20.0,
        "screen_type": "PVC",
    }
    response = client.post("/thing/well-screen", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert data["detail"][0]["msg"] == f"Thing with ID {bad_thing_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": bad_thing_id}


def test_well_add_well_screen_409_wrong_thing_type(spring_thing):
    payload = {
        "thing_id": spring_thing.id,
        "screen_depth_top": 10.0,
        "screen_depth_bottom": 20.0,
        "screen_type": "PVC",
    }
    response = client.post("/thing/well-screen", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {spring_thing.id} is not a water well Thing. It is a spring Thing."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": spring_thing.id}


def test_add_well_screen_409_bad_screen_type(water_well_thing):
    payload = {
        "thing_id": water_well_thing.id,
        "screen_depth_top": 10.0,
        "screen_depth_bottom": 20.0,
        "screen_type": "NotARealType",
    }
    response = client.post("/thing/well-screen", json=payload)

    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "screen_type"]
    assert (
        data["detail"][0]["msg"]
        == f"{payload['screen_type']} is an invalid screen type. Valid types are: PVC | Steel | Concrete."
    )
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"screen_type": payload["screen_type"]}


def test_add_thing_link(spring_thing):
    payload = {
        "thing_id": spring_thing.id,
        "relation": "same_as",
        "alternate_id": "4321-1234",
        "alternate_organization": "USGS",
    }
    response = client.post("/thing/id-link", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["thing_id"] == spring_thing.id
    assert data["relation"] == payload["relation"]
    assert data["alternate_id"] == payload["alternate_id"]
    assert data["alternate_organization"] == payload["alternate_organization"]

    cleanup_post_test(ThingIdLink, data["id"])


def test_add_thing_id_link_409_bad_thing_id():
    bad_thing_id = 9999
    payload = {
        "thing_id": bad_thing_id,
        "relation": "same_as",
        "alternate_id": "4321-1234",
        "alternate_organization": "USGS",
    }
    response = client.post("/thing/id-link", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert data["detail"][0]["msg"] == f"Thing with ID {bad_thing_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": bad_thing_id}


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


def test_get_well_screens(well_screen):
    response = client.get("/thing/well-screen")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == well_screen.id
    assert data["items"][0]["thing_id"] == well_screen.thing_id
    assert data["items"][0]["screen_depth_top"] == well_screen.screen_depth_top
    assert data["items"][0]["screen_depth_bottom"] == well_screen.screen_depth_bottom
    assert data["items"][0]["screen_type"] == well_screen.screen_type
    assert data["items"][0]["screen_description"] == well_screen.screen_description


def test_get_well_screen_by_id(well_screen):
    response = client.get(f"/thing/well-screen/{well_screen.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == well_screen.id
    assert data["thing_id"] == well_screen.thing_id
    assert data["screen_depth_top"] == well_screen.screen_depth_top
    assert data["screen_depth_bottom"] == well_screen.screen_depth_bottom
    assert data["screen_type"] == well_screen.screen_type
    assert data["screen_description"] == well_screen.screen_description


def test_get_well_screen_by_id_404_not_found(well_screen):
    bad_id = 99999
    response = client.get(f"/thing/well-screen/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == f"WellScreen with ID {bad_id} not found."


def test_get_well_screens_by_water_well(water_well_thing, well_screen):
    response = client.get(f"/thing/water-well/{water_well_thing.id}/well-screen")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == well_screen.id
    assert data["items"][0]["thing_id"] == well_screen.thing_id
    assert data["items"][0]["screen_depth_top"] == well_screen.screen_depth_top
    assert data["items"][0]["screen_depth_bottom"] == well_screen.screen_depth_bottom
    assert data["items"][0]["screen_type"] == well_screen.screen_type
    assert data["items"][0]["screen_description"] == well_screen.screen_description


def test_get_well_screens_by_water_well_id_404_not_found(water_well_thing, well_screen):
    bad_id = 99999
    response = client.get(f"/thing/water-well/{bad_id}/well-screen")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_get_well_screens_by_water_well_id_404_wrong_type(spring_thing):
    response = client.get(f"/thing/water-well/{spring_thing.id}/well-screen")
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {spring_thing.id} is not a water well Thing. It is a spring Thing."
    )
    assert data["detail"][0]["loc"] == ["path", "thing_id"]
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": spring_thing.id}


def test_get_thing_id_links(thing_id_link):
    response = client.get("/thing/id-link")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == thing_id_link.id
    assert data["items"][0]["thing_id"] == thing_id_link.thing_id
    assert data["items"][0]["relation"] == thing_id_link.relation
    assert data["items"][0]["alternate_id"] == thing_id_link.alternate_id
    assert (
        data["items"][0]["alternate_organization"]
        == thing_id_link.alternate_organization
    )


def test_get_thing_id_link_by_id(thing_id_link):
    response = client.get(f"/thing/id-link/{thing_id_link.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == thing_id_link.id
    assert data["thing_id"] == thing_id_link.thing_id
    assert data["relation"] == thing_id_link.relation
    assert data["alternate_id"] == thing_id_link.alternate_id
    assert data["alternate_organization"] == thing_id_link.alternate_organization


def test_get_thing_id_link_by_id_404_not_found(thing_id_link):
    bad_id = 99999
    response = client.get(f"/thing/id-link/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == f"ThingIdLink with ID {bad_id} not found."


def test_get_thing_links_by_thing_id(water_well_thing, thing_id_link):
    response = client.get(f"/thing/{water_well_thing.id}/id-link")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == thing_id_link.id
    assert data["items"][0]["thing_id"] == thing_id_link.thing_id
    assert data["items"][0]["relation"] == thing_id_link.relation
    assert data["items"][0]["alternate_id"] == thing_id_link.alternate_id
    assert (
        data["items"][0]["alternate_organization"]
        == thing_id_link.alternate_organization
    )


def test_get_thing_links_by_thing_id_404_not_found(water_well_thing, thing_id_link):
    bad_id = 99999
    response = client.get(f"/thing/{bad_id}/id-link")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_get_things(water_well_thing, spring_thing):
    response = client.get("/thing")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2

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
    assert data["items"][0]["spring_type"] is None

    assert data["items"][1]["id"] == spring_thing.id
    assert data["items"][1][
        "created_at"
    ] == spring_thing.created_at.isoformat().replace("+00:00", "Z")
    assert data["items"][1]["name"] == spring_thing.name
    assert data["items"][1]["thing_type"] == spring_thing.thing_type
    assert data["items"][1]["release_status"] == spring_thing.release_status
    assert data["items"][1]["spring_type"] == spring_thing.spring_type
    assert data["items"][1]["well_type"] is None
    assert data["items"][1]["well_depth"] is None
    assert data["items"][1]["hole_depth"] is None
    assert data["items"][1]["well_construction_notes"] is None


def test_get_thing_by_id(water_well_thing):
    response = client.get(f"/thing/{water_well_thing.id}")
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
    assert data["spring_type"] is None


def test_get_thing_by_id_404_not_found(water_well_thing):
    bad_id = 99999
    response = client.get(f"/thing/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


# # weaver tests
# def test_weaver_get_wells_geojson():
#     response = client.get("/geospatial", params={"type": "well"})
#     assert response.status_code == 200
#     data = response.json()
#     assert "type" in data
#     assert data["type"] == "FeatureCollection"
#     assert len(data["features"]) > 0
#     assert "id" in data["features"][0]["properties"]


# def test_weaver_get_all_collabnet_wells():
#     response = client.get(
#         "/geospatial", params={"type": "well", "group": "collabnet"}
#     )  # TODO: QUESTION: use type filter and a group filter instead of /collabnet endpoint?
#     assert response.status_code == 200
#     data = response.json()

#     assert "features" in data
#     assert len(data["features"]) > 0
#     for feature in data["features"]:
#         assert "geometry" in feature
#         assert isinstance(feature["geometry"], dict)
#         assert "properties" in feature
#         assert isinstance(feature["properties"], dict)
#         assert "coordinates" in feature["geometry"]
#         assert "id" in feature or "name" in feature["properties"]
#         assert "group" in feature["properties"]


# def test_weaver_thing_contact_info_by_id():
#     response = client.get("/contact?thing_id=1")  # or something like this
#     assert response.status_code == 200
#     data = response.json()
#     assert isinstance(data, dict)
#     assert "items" in data
#     assert len(data["items"]) > 0
#     item = data["items"][0]
#     assert "id" in item
#     assert "name" in item
#     assert "addresses" in item
#     assert "emails" in item
#     assert "phones" in item

#     assert isinstance(item["addresses"], list)
#     assert isinstance(item["emails"], list)
#     assert isinstance(item["phones"], list)


# PATCH tests ==================================================================


def test_patch_water_well(water_well_thing):
    payload = {
        "name": "patched water well",
        "release_status": "provisional",
        "well_type": "Injection",
        "well_depth": 20,
        "hole_depth": 40,
        "well_construction_notes": "patched well construction notes",
    }
    response = client.patch(f"/thing/water-well/{water_well_thing.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["release_status"] == payload["release_status"]
    assert data["well_type"] == payload["well_type"]
    assert data["well_depth"] == payload["well_depth"]
    assert data["hole_depth"] == payload["hole_depth"]
    assert data["well_construction_notes"] == payload["well_construction_notes"]

    cleanup_patch_test(Thing, payload, water_well_thing)


def test_patch_water_well_404_not_found():
    bad_id = 99999
    payload = {
        "name": "patched water well",
        "release_status": "provisional",
        "well_type": "Injection",
        "well_depth": 20,
        "hole_depth": 40,
        "well_construction_notes": "patched well construction notes",
    }
    response = client.patch(f"/thing/water-well/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_patch_water_well_404_wrong_type(spring_thing):
    payload = {
        "name": "patched water well",
        "release_status": "provisional",
        "well_type": "Injection",
        "well_depth": 20,
        "hole_depth": 40,
        "well_construction_notes": "patched well construction notes",
    }
    response = client.patch(f"/thing/water-well/{spring_thing.id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {spring_thing.id} is not a water well Thing. It is a spring Thing."
    )
    assert data["detail"][0]["loc"] == ["path", "thing_id"]
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": spring_thing.id}


def test_patch_spring(spring_thing):
    payload = {
        "name": "patched spring",
        "release_status": "private",
        "spring_type": "Mineral",
    }
    response = client.patch(f"/thing/spring/{spring_thing.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["release_status"] == payload["release_status"]
    assert data["spring_type"] == payload["spring_type"]

    cleanup_patch_test(Thing, payload, spring_thing)


def test_patch_spring_404_not_found(spring_thing):
    bad_id = 99999
    payload = {
        "name": "patched spring",
        "release_status": "private",
        "spring_type": "Mineral",
    }
    response = client.patch(f"/thing/spring/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_patch_spring_404_wrong_type(water_well_thing):
    payload = {
        "name": "patched spring",
        "release_status": "private",
        "spring_type": "Mineral",
    }
    response = client.patch(f"/thing/spring/{water_well_thing.id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"][0]["msg"]
        == f"Thing with ID {water_well_thing.id} is not a spring Thing. It is a water well Thing."
    )
    assert data["detail"][0]["loc"] == ["path", "thing_id"]
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": water_well_thing.id}
