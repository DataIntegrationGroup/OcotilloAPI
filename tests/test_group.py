from geoalchemy2.shape import to_shape
from pydantic import ValidationError
import pytest
from datetime import timezone

from db import Group
from core.dependencies import admin_function, viewer_function, editor_function
from main import app
from schemas.group import ValidateGroup
from tests import client, override_authentication, cleanup_post_test, cleanup_patch_test


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():

    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# VALIDATION tests =============================================================


def test_project_area_not_topologically_valid():
    wkt = "MULTIPOLYGON(((0 0, 1 1, 2 2, 0 0)))"
    with pytest.raises(
        ValidationError, match="WKT geometry is not topologically valid"
    ):
        ValidateGroup(project_area=wkt)


def test_project_area_invalid_wkt():
    for wkt in [
        "MULTIPOLYGON((0 0, 1 1, 2 2, 0 0))",
        "0 0, 1 1, 2 2, 3 3, 4 5, 0 0",
    ]:
        with pytest.raises(ValidationError, match=r"Invalid WKT geometry: "):
            ValidateGroup(project_area=wkt)


def test_project_area_not_multipolygon():
    for wkt in [
        "POINT (0 0)",
        "LINESTRING (0 0, 1 1, 2 2, 3 3)",
        "POLYGON ((0 0, 1 1, 2 2, 1 2, 0 0))",
    ]:
        with pytest.raises(ValidationError, match="WKT must be a valid MULTIPOLYGON"):
            ValidateGroup(project_area=wkt)


#  ADD tests ======================================================


def test_add_group():
    payload = {
        "release_status": "private",
        "name": "Test Group",
        "description": "This is a test group.",
        "project_area": "MULTIPOLYGON (((0 0, 1 1, 2 2, 3 3, 4 4, 1 2, 0 0)))",
    }
    response = client.post("/group", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["release_status"] == payload["release_status"]
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]
    assert data["project_area"] == payload["project_area"]

    cleanup_post_test(Group, data["id"])


# GET tests ======================================================


def test_get_groups(group):
    response = client.get("/group")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == group.id
    assert data["items"][0]["created_at"] == group.created_at.astimezone(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert data["items"][0]["release_status"] == group.release_status
    assert data["items"][0]["name"] == group.name
    assert data["items"][0]["project_area"] == to_shape(group.project_area).wkt
    assert data["items"][0]["description"] == group.description
    assert data["items"][0]["parent_group_id"] == group.parent_group_id


def test_get_group_by_id(group):
    response = client.get(f"/group/{group.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group.id
    assert data["created_at"] == group.created_at.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    assert data["name"] == group.name
    assert data["project_area"] == to_shape(group.project_area).wkt
    assert data["description"] == group.description
    assert data["parent_group_id"] == group.parent_group_id
    assert data["release_status"] == group.release_status


def test_get_group_by_id_404_not_found(group):
    bad_id = 99999
    response = client.get(f"/group/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Group with ID {bad_id} not found."


@pytest.mark.skip("associations not yet implemented")
def test_get_group_things():
    response = client.get("/group/association")
    assert response.status_code == 200
    assert len(response.json()) > 0


# PATCH tests ==================================================================


def test_patch_group(group):
    payload = {"name": "Updated Group", "release_status": "private"}
    response = client.patch(f"/group/{group.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group.id
    assert data["name"] == payload["name"]
    assert data["release_status"] == payload["release_status"]

    cleanup_patch_test(Group, payload, group)


def test_patch_group_404_not_found(group):
    payload = {"name": "Failed group patch"}
    bad_id = 99999
    response = client.patch(f"/group/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Group with ID {bad_id} not found."


# DELETE tests =================================================================


def test_delete_group(second_group):
    response = client.delete(f"/group/{second_group.id}")
    assert response.status_code == 204

    # verify deletion
    response = client.get(f"/group/{second_group.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Group with ID {second_group.id} not found."


def test_delete_group_404_not_found(second_group):
    bad_id = 99999
    response = client.delete(f"/group/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Group with ID {bad_id} not found."
