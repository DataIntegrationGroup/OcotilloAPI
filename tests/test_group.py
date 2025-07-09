# from fastapi.testclient import TestClient
# from main import app
# from models import Base, engine
import pytest

from db import Thing
from db.engine import get_db_session

# Base.metadata.drop_all(engine)
# Base.metadata.create_all(engine)

# client = TestClient(app)

from tests import client


#  ADD tests ======================================================


def test_add_group():
    response = client.post("/group", json={"name": "Test Group"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Group"


@pytest.fixture(scope="function")
def thing():
    session = next(get_db_session())
    thing = Thing()
    thing.name = "Test Thing"
    session.add(thing)
    session.commit()
    yield thing

    session.close()


def test_add_group_thing(thing):
    response = client.post(
        "/group/association", json={"group_id": 1, "thing_id": thing.id}
    )
    assert response.status_code == 201

    data = response.json()
    assert "id" in data
    assert data["group_id"] == 1
    assert data["thing_id"] == thing.id


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
    response = client.get("/group/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Group"


def test_item_get_group_thing():
    response = client.get("/group/association/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["group_id"] == 1
    assert data["thing_id"] == 3
