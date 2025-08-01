# from fastapi.testclient import TestClient
# from main import app
# from models import Base, engine
# Base.metadata.drop_all(engine)
# Base.metadata.create_all(engine)

# client = TestClient(app)

from tests import client


#  ADD tests ======================================================


def test_add_contact(thing):
    response = client.post(
        "/contact",
        json={
            "name": "Test Contact",
            "role": "Owner",
            "thing_id": thing.id,
            "emails": [{"email": "fasdfasdf@gmail.com", "email_type": "Primary"}],
            "phones": [{"phone_number": "+12345678901", "phone_type": "Primary"}],
            "addresses": [
                {
                    "address_line_1": "123 Main St",
                    "city": "Test City",
                    "state": "NM",
                    "postal_code": "87501",
                    "country": "United States",
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


def test_phone_validation_fail(thing):
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
            "/contact",
            json={
                "name": "Test Contact 2",
                "thing_id": thing.id,
                "role": "Primary",
                "emails": [{"email": "fasdfasdf@gmail.com", "email_type": "Primary"}],
                "phones": [{"phone_number": phone, "phone_type": "Primary"}],
                "addresses": [
                    {
                        "address_line_1": "123 Main St",
                        "city": "Test City",
                        "state": "NM",
                        "postal_code": "87501",
                        "country": "United States",
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


def test_email_validation_fail(thing):

    for email in [
        "",
        "invalid-email",
        "invalid@domain",
        "invalid@domain.",
        "@domain.com",
    ]:
        response = client.post(
            "/contact",
            json={
                "name": "Test ContactX",
                "thing_id": thing.id,
                "role": "Primary",
                "emails": [{"email": email, "email_type": "Primary"}],
                "phones": [{"phone_number": "+12345678901", "phone_type": "Primary"}],
                "addresses": [
                    {
                        "address_line_1": "123 Main St",
                        "city": "Test City",
                        "state": "NM",
                        "postal_code": "87501",
                        "country": "United States",
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


def test_get_contacts():
    response = client.get("/contact")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data, "Expected 'items' in response"
    items = data["items"]
    assert isinstance(items, list), "'items' should be a list"
    assert len(items) > 0, "'items' should not be empty"
    item = items[0]
    assert "id" in item, "Expected 'id' in contact item"
    assert "name" in item, "Expected 'name' in contact item"
    assert "role" in item, "Expected 'role' in contact item"
    assert "emails" in item, "Expected 'emails' in contact item"
    assert "phones" in item, "Expected 'phones' in contact item"
    assert "addresses" in item, "Expected 'addresses' in contact item"
    assert isinstance(item["emails"], list), "'emails' should be a list"
    assert isinstance(item["phones"], list), "'phones' should be a list"
    assert isinstance(item["addresses"], list), "'addresses' should be a list"
    assert len(item["emails"]) == 1, "'emails' should not be empty"
    assert len(item["phones"]) == 1, "'phones' should not be empty"
    assert len(item["addresses"]) == 1, "'addresses' should not be empty"

    # print(response.json())
    # assert len(response.json()) > 0


def test_get_email_by_contact_id():
    response = client.get("/contact/1/email")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Expected a paginated response"
    assert "items" in data, "Expected 'items' in response"
    data = data["items"]
    assert len(data) == 1, "Expected one phone number"
    email = data[0]
    assert "id" in email, "Expected 'id' in email item"
    assert "email" in email, "Expected 'email' in email item"
    assert "email_type" in email, "Expected 'email_type' in email item"


def test_get_phone_by_contact_id():
    response = client.get("/contact/1/phone")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict), "Expected a paginated response"
    assert "items" in data, "Expected 'items' in response"
    data = data["items"]
    assert len(data) == 1, "Expected one phone number"
    phone = data[0]
    assert "id" in phone, "Expected 'id' in phone item"
    assert "phone_number" in phone, "Expected 'phone_number' in phone item"
    assert "phone_type" in phone, "Expected 'phone_type' in phone item"


def test_get_address_by_contact_id():
    response = client.get("/contact/1/address")
    data = response.json()
    assert response.status_code == 200
    assert isinstance(data, dict), "Expected a paginated response"
    assert "items" in data, "Expected 'items' in response"
    data = data["items"]
    assert len(data) == 1, "Expected one phone number"
    address = data[0]
    assert "id" in address, "Expected 'id' in address item"
    assert "address_line_1" in address, "Expected 'address_line_1' in address item"
    assert "city" in address, "Expected 'city' in address item"
    assert "state" in address, "Expected 'state' in address item"
    assert "postal_code" in address, "Expected 'postal_code' in address item"
    assert "country" in address, "Expected 'country' in address item"
    assert "address_type" in address, "Expected 'address_type' in address item"


# test item retrieval via filter ===========================================


# Test item retrieval ======================================================
def test_item_get_contact():
    response = client.get("/contact/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Test Contact"

    assert "emails" in data
    emails = data["emails"]
    assert len(emails) == 1
    email = emails[0]
    assert email["email"] == "fasdfasdf@gmail.com"
    assert email["email_type"] == "Primary"

    assert "phones" in data
    phones = data["phones"]
    assert len(phones) == 1
    phone = phones[0]
    assert phone["phone_number"] == "+12345678901"
    assert phone["phone_type"] == "Primary"

    assert "addresses" in data
    addresses = data["addresses"]
    assert len(addresses) == 1
    address = addresses[0]
    assert address["address_line_1"] == "123 Main St"
    assert address["city"] == "Test City"
    assert address["state"] == "NM"
    assert address["postal_code"] == "87501"
    assert address["country"] == "United States"
    assert address["address_type"] == "Primary"


# Test item edit ==========================================================
def test_item_edit_contact_name():
    response = client.patch(
        "/contact/1",
        json={
            "name": "Updated Contact",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Updated Contact"
    assert data["role"] == "Owner"

    # put contact name back to original
    response = client.patch(
        "/contact/1",
        json={
            "name": "Test Contact",
        },
    )
    assert response.status_code == 200


def test_edit_contact_email():
    response = client.patch("/contact/email/1", json={"email": "boo@bar.com"})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["email"] == "boo@bar.com"
    assert data["email_type"] == "Primary"

    # put contact email back to original
    response = client.patch("/contact/email/1", json={"email": "fasdfasdf@gmail.com"})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["email"] == "fasdfasdf@gmail.com"


def test_edit_contact_phone():
    response = client.patch("/contact/phone/1", json={"phone_number": "+19876543210"})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["phone_number"] == "+19876543210"

    # put contact phone back to original
    response = client.patch("/contact/phone/1", json={"phone_number": "+12345678901"})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["phone_number"] == "+12345678901"


def test_edit_contact_address():
    response = client.patch(
        "/contact/address/1",
        json={
            "address_line_1": "456 Elm St",
            "city": "Updated City",
            "postal_code": "90210",
            "country": "United States",
        },
    )
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["address_line_1"] == "456 Elm St"
    assert data["city"] == "Updated City"
    assert data["state"] == "NM"
    assert data["postal_code"] == "90210"
    assert data["country"] == "United States"
    assert data["address_type"] == "Primary"

    # put contact address back to original
    response = client.patch(
        "/contact/address/1",
        json={
            "address_line_1": "123 Main St",
            "city": "Test City",
            "state": "NM",
            "postal_code": "87501",
            "country": "United States",
            "address_type": "Primary",
        },
    )
    data = response.json()
    assert response.status_code == 200
