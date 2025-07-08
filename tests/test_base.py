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
@pytest.mark.skip
def test_add_group():
    response = client.post("/base/group", json={"name": "Test Group"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Group"


@pytest.mark.skip
def test_add_group_location():
    response = client.post(
        "/base/group_location", json={"group_id": 1, "location_id": 1}
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["group_id"] == 1
    assert data["location_id"] == 1


@pytest.fixture(scope='function')
def thing():
    session = next(get_db_session())
    thing = Thing()
    session.add(thing)
    session.commit()
    yield

    session.close()


def test_add_contact(thing):
    response = client.post(
        "/base/contact",
        json={
            "name": "Test Contact",
            "role": "Owner",
            "thing_id": 1,
            "emails": [{"email": "fasdfasdf@gmail.com", "email_type": "Primary"}],
            "phones": [{"phone_number": "+12345678901", "phone_type": "Primary"}],
            "addresses": [
                {
                    "address_line_1": "123 Main St",
                    "city": "Test City",
                    "state": "NM",
                    "postal_code": "87501",
                    "country": "US",
                    "address_type": "Primary",
                }
            ],
        },
    )
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert data["name"] == "Test Contact"
    assert data["role"] == "Owner"

    assert len(data["emails"]) == 1
    assert data["emails"][0]["email"] == "fasdfasdf@gmail.com"

    assert len(data["phones"]) == 1
    assert data["phones"][0]["phone_number"] == "+12345678901"
    assert len(data["addresses"]) == 1
    assert data["addresses"][0]["address_line_1"] == "123 Main St"

    # assert data["email"] == "fasdfasdf@gmail.com"

    # for i in range(2, 5):
    #     response = client.post(
    #         "/base/contact",
    #         json={
    #             "owner_id": i,
    #             "name": f"Test Contact {i}",
    #             "email": f"foo{i}@gmail.com",
    #             "phone": f"+1234567890{i}",
    #         },
    #     )
    #     assert response.status_code == 201
    #     data = response.json()
    #     assert "id" in data
    #     assert data["name"] == f"Test Contact {i}"
    #     assert data["email"] == f"foo{i}@gmail.com"
    #     assert data["phone"] == f"+1234567890{i}"


def test_phone_validation_fail():
    for phone in [
        "definitely not a phone",
        # "1234567890",
        # "123-456-7890",
        # "123-456-78901",
        # "123-4567-890",
        "123-456-789a",
        "123-456-7890x1234",
        "123.456.7890",
        "(123) 456-7890",
    ]:

        response = client.post(
            "/base/contact",
            json={
                "name": "Test Contact 2",
                "thing_id": 1,
                "role": "Primary",
                "emails": [{"email": "fasdfasdf@gmail.com", "email_type": "Primary"}],
                "phones": [{"phone_number": phone, "phone_type": "Primary"}],
                "addresses": [
                    {
                        "address_line_1": "123 Main St",
                        "city": "Test City",
                        "state": "NM",
                        "postal_code": "87501",
                        "country": "US",
                        "address_type": "Primary",
                    }
                ],
            },
        )
        data = response.json()
        assert response.status_code == 422
        assert "detail" in data, "Expected 'detail' in response"
        assert len(data["detail"]) == 1, "Expected 1 error in response"
        detail = data["detail"][0]
        assert detail["msg"] == f"Value error, Invalid phone number. {phone}"


def test_email_validation_fail():

    for email in [
        "",
        "invalid-email",
        "invalid@domain",
        "invalid@domain.",
        "@domain.com",
    ]:
        response = client.post(
            "/base/contact",
            json={
                "name": "Test ContactX",
                "thing_id": 1,
                "role": "Primary",
                "emails": [{"email": email, "email_type": "Primary"}],
                "phones": [{"phone_number": "+12345678901", "phone_type": "Primary"}],
                "addresses": [
                    {
                        "address_line_1": "123 Main St",
                        "city": "Test City",
                        "state": "NM",
                        "postal_code": "87501",
                        "country": "US",
                        "address_type": "Primary",
                    }
                ],
            },
        )
        data = response.json()
        assert response.status_code == 422
        assert "detail" in data, "Expected 'detail' in response"
        assert len(data["detail"]) == 1, "Expected 1 error in response"
        detail = data["detail"][0]
        assert detail["msg"] == f"Value error, Invalid email format. {email}"



# GET tests ======================================================





# def test_get_locations():
#     response = client.get("/base/location")
#     assert response.status_code == 200
#     assert len(response.json()) > 0

@pytest.mark.skip
def test_get_groups():
    response = client.get("/base/group")
    assert response.status_code == 200
    assert len(response.json()) > 0


def test_get_contacts():
    response = client.get("/base/contact")
    assert response.status_code == 200
    assert len(response.json()) > 0




@pytest.mark.skip
def test_get_group_locations():
    response = client.get("/base/group_location")
    assert response.status_code == 200
    assert len(response.json()) > 0


# test item retrieval via filter ===========================================



# Test item retrieval ======================================================
@pytest.mark.skip
def test_item_get_spring():
    response = client.get("/base/spring/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["location_id"] == 1

@pytest.mark.skip
def test_item_get_location():
    response = client.get("/base/location/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Location 1"
    assert "well" not in data

@pytest.mark.skip
def test_item_get_group():
    response = client.get("/base/group/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Group"

@pytest.mark.skip
def test_item_get_wells():
    response = client.get("/base/well/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["location_id"] == 1

@pytest.mark.skip
def test_item_get_well_screens():
    response = client.get("/base/wellscreen/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["well_id"] == 1
    assert data["screen_depth_top"] == 10.0
    assert data["screen_depth_bottom"] == 20.0

@pytest.mark.skip
def test_item_get_group_locations():
    response = client.get("/base/group_location/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["group_id"] == 1
    assert data["location_id"] == 1


def test_item_get_contact():
    response = client.get("/base/contact/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Contact"
    # assert data["email"] == "fasdfasdf@gmail.com"
    # assert data["phone"] == "+12345678901"
