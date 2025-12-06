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

from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)
from db import Thing, WellScreen, ThingIdLink
from main import app
from schemas import DT_FMT
from schemas.location import LocationResponse
from schemas.thing import ValidateWell
from tests import (
    client,
    override_authentication,
    cleanup_post_test,
    cleanup_patch_test,
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


# VALIDATE tests ===============================================================


def test_validate_hole_depth_well_depth():
    with pytest.raises(
        ValueError, match="well depth must be less than than or equal to hole depth"
    ):
        ValidateWell(well_depth=100.0, hole_depth=90.0)


def test_validate_hole_depth_casing_depth():
    with pytest.raises(
        ValueError,
        match="well casing depth must be less than or equal to hole depth",
    ):
        ValidateWell(hole_depth=100.0, well_casing_depth=110.0)


# this is not a valid test because measuring_point_height is not related to hole_depth
# def test_validate_mp_height_hole_depth():
#     with pytest.raises(
#         ValueError,
#         match="measuring point height must be less than hole depth",
#     ):
#         ValidateWell(hole_depth=100.0, measuring_point_height=110.0)
#
#
# def test_validate_mp_height_well_depth():
#     with pytest.raises(
#         ValueError,
#         match="measuring point height must be less than well depth",
#     ):
#         ValidateWell(well_depth=100.0, measuring_point_height=105.0)
#
#
# def test_validate_mp_height_well_casing_depth():
#     with pytest.raises(
#         ValueError,
#         match="measuring point height must be less than well casing depth",
#     ):
#         ValidateWell(well_casing_depth=100.0, measuring_point_height=105.0)
#

# POST tests ===================================================================


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_water_well(location, group):
    payload = {
        "location_id": location.id,
        "group_id": group.id,
        "release_status": "draft",
        "name": "Test Well",
        "first_visit_date": "2023-01-01",
        "well_depth": 100.0,
        "hole_depth": 110,
        "well_construction_notes": "this is a test of notes",
        "well_casing_diameter": 5.0,
        "well_casing_depth": 10.0,
        "well_casing_materials": ["PVC"],
        "well_purposes": ["Domestic"],
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
    assert data["name"] == payload["name"]
    assert data["first_visit_date"] == payload["first_visit_date"]
    assert data["thing_type"] == "water well"
    assert data["well_purposes"] == payload["well_purposes"]
    assert data["hole_depth"] == payload["hole_depth"]
    assert data["hole_depth_unit"] == "ft"
    assert data["well_depth"] == payload["well_depth"]
    assert data["well_depth_unit"] == "ft"
    assert data["well_construction_notes"] == payload["well_construction_notes"]
    assert data["well_casing_diameter"] == payload["well_casing_diameter"]
    assert data["well_casing_diameter_unit"] == "in"
    assert data["well_casing_depth"] == payload["well_casing_depth"]
    assert data["well_casing_depth_unit"] == "ft"
    assert data["well_casing_materials"] == payload["well_casing_materials"]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location

    cleanup_post_test(Thing, data["id"])


@pytest.mark.skip(
    "This duplicates the test above. That one will need to eventually be updated"
)
def test_add_water_well_with_measuring_point(location, group):
    """
    Test creating a well with measuring_point_height and measuring_point_description.

    This reproduces the bug where measuring_point fields are properties (from MeasuringPointHistory table)
    and cannot be set directly on Thing objects.

    Expected error (before fix): AttributeError: property 'measuring_point_height' of 'Thing' object has no setter
    """
    payload = {
        "location_id": location.id,
        "group_id": group.id,
        "release_status": "draft",
        "name": "Test Well with Measuring Point",
        "measuring_point_height": 2.5,
        "measuring_point_description": "top of casing",
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == payload["name"]
    assert data["measuring_point_height"] == 2.5
    assert data["measuring_point_description"] == "top of casing"

    cleanup_post_test(Thing, data["id"])


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_water_well_409_bad_group_id(location):
    bad_group_id = 9999
    payload = {
        "location_id": location.id,
        "group_id": bad_group_id,  # Invalid group ID
        "release_status": "draft",
        "name": "Test Well",
        "first_visit_date": "2023-01-01",
        "well_purposes": ["Domestic"],
        "well_depth": 100.0,
        "hole_depth": 110,
        "well_construction_notes": "this is a test of notes",
        "well_casing_diameter": 5.0,
        "well_casing_depth": 10.0,
    }

    response = client.post("/thing/water-well", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "group_id"]
    assert data["detail"][0]["msg"] == f"Group with ID {bad_group_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"group_id": bad_group_id}


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_water_well_409_bad_location_id(group):
    bad_location_id = 9999
    payload = {
        "location_id": bad_location_id,
        "group_id": group.id,  # Invalid group ID
        "release_status": "draft",
        "name": "Test Well",
        "first_visit_date": "2023-01-01",
        "well_purposes": ["Domestic"],
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


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_spring(location, group):
    payload = {
        "location_id": location.id,
        "group_id": group.id,
        "name": "test spring",
        "first_visit_date": "2023-01-01",
        "release_status": "draft",
        "spring_type": "Ephemeral",
    }
    response = client.post("/thing/spring", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["name"] == payload["name"]
    assert data["first_visit_date"] == payload["first_visit_date"]
    assert data["release_status"] == payload["release_status"]
    assert data["spring_type"] == payload["spring_type"]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location

    cleanup_post_test(Thing, data["id"])


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_spring_409_bad_group_id(location):
    bad_group_id = 9999
    payload = {
        "location_id": location.id,
        "group_id": bad_group_id,  # Invalid group ID
        "name": "test spring",
        "first_visit_date": "2023-01-01",
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


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_add_spring_409_bad_location_id(group):
    bad_location_id = 9999
    payload = {
        "location_id": bad_location_id,
        "group_id": group.id,  # Invalid group ID
        "name": "test spring",
        "first_visit_date": "2023-01-01",
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
        "release_status": "draft",
    }
    response = client.post("/thing/well-screen", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
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
        "release_status": "draft",
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
        "release_status": "draft",
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


def test_add_well_screen_422_bad_screen_type(water_well_thing):
    payload = {
        "thing_id": water_well_thing.id,
        "screen_depth_top": 10.0,
        "screen_depth_bottom": 20.0,
        "screen_type": "NotARealType",
        "release_status": "draft",
    }
    response = client.post("/thing/well-screen", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "screen_type"]
    assert data["detail"][0]["msg"] == "Input should be 'PVC', 'Steel' or 'Concrete'"
    assert data["detail"][0]["type"] == "enum"
    assert data["detail"][0]["input"] == payload["screen_type"]


def test_add_thing_link(spring_thing):
    payload = {
        "thing_id": spring_thing.id,
        "relation": "same_as",
        "alternate_id": "4321-1234",
        "alternate_organization": "USGS",
        "release_status": "draft",
    }
    response = client.post("/thing/id-link", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
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
        "release_status": "draft",
    }
    response = client.post("/thing/id-link", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "thing_id"]
    assert data["detail"][0]["msg"] == f"Thing with ID {bad_thing_id} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"thing_id": bad_thing_id}


# GET tests ====================================================================


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_get_water_wells(water_well_thing, location):
    response = client.get("/thing/water-well")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == water_well_thing.id
    assert data["items"][0]["created_at"] == water_well_thing.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["name"] == water_well_thing.name
    assert (
        data["items"][0]["first_visit_date"]
        == water_well_thing.first_visit_date.isoformat()
    )
    assert data["items"][0]["thing_type"] == water_well_thing.thing_type
    assert data["items"][0]["release_status"] == water_well_thing.release_status
    assert data["items"][0]["well_purposes"] == [
        p for p in water_well_thing.well_purposes
    ]
    assert data["items"][0]["well_depth"] == water_well_thing.well_depth
    assert data["items"][0]["well_depth_unit"] == "ft"
    assert data["items"][0]["hole_depth"] == water_well_thing.hole_depth
    assert data["items"][0]["hole_depth_unit"] == "ft"
    assert (
        data["items"][0]["well_construction_notes"]
        == water_well_thing.well_construction_notes
    )
    assert (
        data["items"][0]["well_casing_diameter"]
        == water_well_thing.well_casing_diameter
    )
    assert data["items"][0]["well_casing_diameter_unit"] == "in"
    assert data["items"][0]["well_casing_depth"] == water_well_thing.well_casing_depth
    assert data["items"][0]["well_casing_depth_unit"] == "ft"
    assert data["items"][0]["well_casing_materials"] == [
        wcm for wcm in water_well_thing.well_casing_materials
    ]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["items"][0]["current_location"] == expected_location


@pytest.mark.skip(
    "This is now tested by well-core-information.feature and well-additional-information.feature"
)
def test_get_water_well_by_id(water_well_thing, location):
    response = client.get(f"/thing/water-well/{water_well_thing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == water_well_thing.id
    assert data["created_at"] == water_well_thing.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["name"] == water_well_thing.name
    assert data["first_visit_date"] == water_well_thing.first_visit_date.isoformat()
    assert data["thing_type"] == water_well_thing.thing_type
    assert data["release_status"] == water_well_thing.release_status
    assert data["well_purposes"] == [p for p in water_well_thing.well_purposes]
    assert data["well_depth"] == water_well_thing.well_depth
    assert data["well_depth_unit"] == "ft"
    assert data["hole_depth"] == water_well_thing.hole_depth
    assert data["hole_depth_unit"] == "ft"
    assert data["well_construction_notes"] == water_well_thing.well_construction_notes
    assert data["well_casing_diameter"] == water_well_thing.well_casing_diameter
    assert data["well_casing_diameter_unit"] == "in"
    assert data["well_casing_depth"] == water_well_thing.well_casing_depth
    assert data["well_casing_depth_unit"] == "ft"
    assert data["well_casing_materials"] == [
        wcm for wcm in water_well_thing.well_casing_materials
    ]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location


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


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_get_springs(spring_thing, location):
    response = client.get("/thing/spring")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == spring_thing.id
    assert data["items"][0]["created_at"] == spring_thing.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["name"] == spring_thing.name
    assert (
        data["items"][0]["first_visit_date"]
        == spring_thing.first_visit_date.isoformat()
    )
    assert data["items"][0]["thing_type"] == spring_thing.thing_type
    assert data["items"][0]["release_status"] == spring_thing.release_status
    assert data["items"][0]["spring_type"] == spring_thing.spring_type
    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["items"][0]["current_location"] == expected_location


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_get_spring_by_id(spring_thing, location):
    response = client.get(f"/thing/spring/{spring_thing.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == spring_thing.id
    assert data["created_at"] == spring_thing.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["name"] == spring_thing.name
    assert data["first_visit_date"] == spring_thing.first_visit_date.isoformat()
    assert data["thing_type"] == spring_thing.thing_type
    assert data["release_status"] == spring_thing.release_status
    assert data["spring_type"] == spring_thing.spring_type
    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location


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
    assert data["items"][0]["release_status"] == well_screen.release_status
    assert data["items"][0]["created_at"] == well_screen.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)


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
    assert data["release_status"] == well_screen.release_status
    assert data["created_at"] == well_screen.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)


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
    assert data["items"][0]["created_at"] == thing_id_link.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["release_status"] == thing_id_link.release_status
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
    assert data["created_at"] == thing_id_link.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["release_status"] == thing_id_link.release_status
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


def test_get_things(water_well_thing, spring_thing, location):
    response = client.get("/thing")
    assert response.status_code == 200

    expected_location = LocationResponse.model_validate(location).model_dump()
    # created_at is already serialized to UTC format by UTCAwareDatetime

    data = response.json()
    assert data["total"] == 2


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_get_thing_by_id(water_well_thing, location):
    response = client.get(f"/thing/{water_well_thing.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == water_well_thing.id
    assert data["created_at"] == water_well_thing.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["release_status"] == water_well_thing.release_status
    assert data["name"] == water_well_thing.name
    assert data["first_visit_date"] == water_well_thing.first_visit_date.isoformat()
    assert data["thing_type"] == water_well_thing.thing_type
    assert data["release_status"] == water_well_thing.release_status
    assert data["well_purposes"] == [p for p in water_well_thing.well_purposes]
    assert data["well_casing_materials"] == [
        cm for cm in water_well_thing.well_casing_materials
    ]
    assert data["well_depth"] == water_well_thing.well_depth
    assert data["hole_depth"] == water_well_thing.hole_depth
    assert data["well_construction_notes"] == water_well_thing.well_construction_notes
    assert data["spring_type"] is None

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location


def test_get_thing_by_id_404_not_found(water_well_thing):
    bad_id = 99999
    response = client.get(f"/thing/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_get_thing_deployments_by_id(
    water_well_thing, sensor_to_water_well_thing_deployment, sensor
):
    response = client.get(f"/thing/{water_well_thing.id}/deployment")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == sensor_to_water_well_thing_deployment.id
    assert data["items"][0]["thing_id"] == water_well_thing.id
    assert data["items"][0]["sensor"]["id"] == sensor.id
    assert (
        data["items"][0]["installation_date"]
        == sensor_to_water_well_thing_deployment.installation_date
    )
    assert (
        data["items"][0]["removal_date"]
        == sensor_to_water_well_thing_deployment.removal_date
    )
    assert (
        data["items"][0]["recording_interval"]
        == sensor_to_water_well_thing_deployment.recording_interval
    )
    assert (
        data["items"][0]["recording_interval_units"]
        == sensor_to_water_well_thing_deployment.recording_interval_units
    )
    assert (
        data["items"][0]["hanging_cable_length"]
        == sensor_to_water_well_thing_deployment.hanging_cable_length
    )
    assert (
        data["items"][0]["hanging_point_height"]
        == sensor_to_water_well_thing_deployment.hanging_point_height
    )
    assert (
        data["items"][0]["hanging_point_description"]
        == sensor_to_water_well_thing_deployment.hanging_point_description
    )
    assert data["items"][0]["notes"] == sensor_to_water_well_thing_deployment.notes


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


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_patch_water_well(water_well_thing, location):
    payload = {
        "name": "patched water well",
        "first_visit_date": "2023-02-02",
        "release_status": "provisional",
        "well_purposes": ["Injection"],
        "well_depth": 20,
        "hole_depth": 40,
        "well_construction_notes": "patched well construction notes",
    }
    response = client.patch(f"/thing/water-well/{water_well_thing.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["first_visit_date"] == payload["first_visit_date"]
    assert data["release_status"] == payload["release_status"]
    assert data["well_purposes"] == payload["well_purposes"]
    assert data["well_depth"] == payload["well_depth"]
    assert data["hole_depth"] == payload["hole_depth"]
    assert data["well_construction_notes"] == payload["well_construction_notes"]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location

    cleanup_patch_test(Thing, payload, water_well_thing)


def test_patch_water_well_404_not_found():
    bad_id = 99999
    payload = {
        "name": "patched water well",
        "first_visit_date": "2023-02-02",
        "release_status": "provisional",
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
        "first_visit_date": "2023-02-02",
        "release_status": "provisional",
        "well_purpose": "Injection",
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


@pytest.mark.skip("Needs to be updated per changes made from feature files")
def test_patch_spring(spring_thing, location):
    payload = {
        "name": "patched spring",
        "first_visit_date": "2023-03-03",
        "release_status": "private",
        "spring_type": "Mineral",
    }
    response = client.patch(f"/thing/spring/{spring_thing.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["first_visit_date"] == payload["first_visit_date"]
    assert data["release_status"] == payload["release_status"]
    assert data["spring_type"] == payload["spring_type"]

    expected_location = LocationResponse.model_validate(location).model_dump(
        mode="json"
    )
    # created_at is already serialized to UTC format by UTCAwareDatetime
    assert data["current_location"] == expected_location

    cleanup_patch_test(Thing, payload, spring_thing)


def test_patch_spring_404_not_found(spring_thing):
    bad_id = 99999
    payload = {
        "name": "patched spring",
        "first_visit_date": "2023-03-03",
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
        "first_visit_date": "2023-03-03",
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


def test_patch_thing_id_link(thing_id_link):
    payload = {
        "relation": "related_to",
        "alternate_id": "9999-8888",
        "alternate_organization": "TWDB",
        "release_status": "draft",
    }
    response = client.patch(f"/thing/id-link/{thing_id_link.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["relation"] == payload["relation"]
    assert data["alternate_id"] == payload["alternate_id"]
    assert data["alternate_organization"] == payload["alternate_organization"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(ThingIdLink, payload, thing_id_link)


def test_patch_thing_id_link_404_not_found():
    bad_id = 9999
    payload = {
        "relation": "related_to",
        "alternate_id": "9999-8888",
        "alternate_organization": "EPA",
    }
    response = client.patch(f"/thing/id-link/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"ThingIdLink with ID {bad_id} not found."


def test_patch_well_screen(well_screen):
    payload = {
        "screen_depth_bottom": 2,
        "screen_depth_top": 1,
        "screen_description": "patched screen description",
        "screen_type": "Steel",
        "release_status": "draft",
    }
    response = client.patch(f"/thing/well-screen/{well_screen.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["screen_depth_bottom"] == payload["screen_depth_bottom"]
    assert data["screen_depth_top"] == payload["screen_depth_top"]
    assert data["screen_description"] == payload["screen_description"]
    assert data["screen_type"] == data["screen_type"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(WellScreen, payload, well_screen)


def test_patch_well_screen_404_not_found():
    bad_id = 9999
    payload = {
        "screen_depth_bottom": 2,
        "screen_depth_top": 1,
        "screen_desciption": "patched screen description",
        "screen_type": "Steel",
    }
    response = client.patch(f"/thing/well-screen/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"WellScreen with ID {bad_id} not found."


# DELETE tests =================================================================


def test_delete_thing(second_spring_thing):
    response = client.delete(f"/thing/{second_spring_thing.id}")
    assert response.status_code == 204

    # Verify the thing is deleted
    response = client.get(f"/thing/spring/{second_spring_thing.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {second_spring_thing.id} not found."


def test_delete_thing_404_not_found():
    bad_id = 9999
    response = client.delete(f"/thing/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Thing with ID {bad_id} not found."


def test_delete_well_screen(second_well_screen):
    response = client.delete(f"/thing/well-screen/{second_well_screen.id}")
    assert response.status_code == 204

    # Verify the well screen is deleted
    response = client.get(f"/thing/well-screen/{second_well_screen.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"WellScreen with ID {second_well_screen.id} not found."


def test_delete_well_screen_404_not_found():
    bad_id = 9999
    response = client.delete(f"/thing/well-screen/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"WellScreen with ID {bad_id} not found."


def test_delete_thing_id_link(second_thing_id_link):
    response = client.delete(f"/thing/id-link/{second_thing_id_link.id}")
    assert response.status_code == 204

    # Verify the thing ID link is deleted
    response = client.get(f"/thing/id-link/{second_thing_id_link.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"ThingIdLink with ID {second_thing_id_link.id} not found."


def test_delete_thing_id_link_404_not_found(second_thing_id_link):
    bad_id = 9999
    response = client.delete(f"/thing/id-link/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"ThingIdLink with ID {bad_id} not found."
