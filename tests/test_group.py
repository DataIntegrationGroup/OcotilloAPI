from geoalchemy2.shape import to_shape
import pytest

from db import Group
from core.dependencies import admin_function, viewer_function, editor_function
from main import app
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


#  ADD tests ======================================================


def test_add_group():
    payload = {
        "name": "Test Group",
        "description": "This is a test group.",
        "project_area": "MULTIPOLYGON (((0 0, 1 1, 2 2, 3 3, 4 4, 1 2, 0 0)))",
    }
    response = client.post("/group", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
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
    assert data["items"][0]["created_at"] == group.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["items"][0]["name"] == group.name
    assert data["items"][0]["project_area"] == to_shape(group.project_area).wkt
    assert data["items"][0]["description"] == group.description
    assert data["items"][0]["parent_group_id"] == group.parent_group_id


def test_get_group_by_id(group):
    response = client.get(f"/group/{group.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group.id
    assert data["created_at"] == group.created_at.isoformat().replace("+00:00", "Z")
    assert data["name"] == group.name
    assert data["project_area"] == to_shape(group.project_area).wkt
    assert data["description"] == group.description
    assert data["parent_group_id"] == group.parent_group_id


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
    payload = {
        "name": "Updated Group",
    }
    response = client.patch(f"/group/{group.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == group.id
    assert data["name"] == payload["name"]

    cleanup_patch_test(Group, payload, group)


def test_patch_group_404_not_found(group):
    payload = {"name": "Failed group patch"}
    bad_id = 99999
    response = client.patch(f"/group/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Group with ID {bad_id} not found."
