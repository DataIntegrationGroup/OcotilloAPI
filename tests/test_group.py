import pytest
from tests import client


#  ADD tests ======================================================


def test_add_group():
    response = client.post("/group", json={"name": "Test Group"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Group"


def test_add_group_with_area():
    response = client.post(
        "/group",
        json={
            "name": "Test Group with Project Area",
            "project_area": "MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, -106.6 34.2, -107.2 34.2, -107.2 33.6)))",
        },
    )
    assert response.status_code == 201
    data = response.json()


# def test_add_group_thing(location, thing):
#     response = client.post(
#         "/group/association", json={"group_id": 2, "thing_id": thing.id}
#     )
#     assert response.status_code == 201
#
#     data = response.json()
#     assert "id" in data
#     assert data["group_id"] == 2
#     assert data["thing_id"] == thing.id


# GET tests ======================================================


def test_get_groups():
    response = client.get("/group")
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.skip
def test_get_group_things():
    response = client.get("/group/association")
    assert response.status_code == 200
    assert len(response.json()) > 0


# test item retrieval via filter ===========================================


# Test item retrieval ======================================================
# @pytest.mark.skip
# def test_item_get_spring():
#     response = client.get("/thing/spring/1")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["id"] == 1
#     assert data["location_id"] == 1


def test_item_get_group():
    response = client.get("/group/2")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert data["name"] == "Test Group"


# def test_item_get_group_thing(location, thing):
#     response = client.get("/group/association/1")
#     assert response.status_code == 200
#     data = response.json()
#     assert data["id"] == 1
#     assert data["group_id"] == 2
#     assert data["thing_id"] == thing.id
