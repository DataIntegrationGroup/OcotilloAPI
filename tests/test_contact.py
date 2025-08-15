from db import Contact, Address, Email, Phone
from db.engine import session_ctx
from tests import client, cleanup_post_test, cleanup_patch_test
from schemas.contact import ValidateEmail, ValidatePhone

import pytest

# ============= module & function fixtures =======================================


@pytest.fixture(scope="function")
def second_contact(thing):
    with session_ctx() as session:
        contact = Contact(
            name="Test Second Contact",
            role="Owner",
        )
        session.add(contact)
        session.commit()
        session.refresh(contact)

        yield contact

        session.close()


@pytest.fixture(scope="function")
def second_email(second_contact):
    with session_ctx() as session:
        email = Email(
            email="testsecondcontact@gmail.com",
            email_type="Primary",
            contact_id=second_contact.id,
        )
        session.add(email)
        session.commit()
        session.refresh(email)
        yield email
        session.close()


@pytest.fixture(scope="function")
def second_phone(second_contact):
    with session_ctx() as session:
        phone = Phone(
            phone_number="123-456-7890",
            phone_type="Primary",
            contact_id=second_contact.id,
        )
        session.add(phone)
        session.commit()
        session.refresh(phone)
        yield phone
        session.close()


@pytest.fixture(scope="function")
def second_address(second_contact):
    with session_ctx() as session:
        address = Address(
            address_line_1="456 Secondary St",
            address_line_2="Apt 12A",
            city="Test Metropolis",
            state="NM",
            postal_code="87501",
            country="United States",
            address_type="Primary",
            contact_id=second_contact.id,
        )
        session.add(address)
        session.commit()
        session.refresh(address)
        yield address
        session.close()


# VALIDATION tests =============================================================


def test_validate_phone(thing):
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
        try:
            new_phone = ValidatePhone(phone_number=phone, phone_type="Primary")
        except Exception as e:
            assert e.errors()[0]["msg"] == f"Value error, Invalid phone number. {phone}"


def test_validate_email(thing):
    for email in [
        "invalid-email",
        "user@.com",
        "user@domain..com",
        "user@domain.com",
    ]:
        try:
            new_email = ValidateEmail(email=email)
        except Exception as e:
            assert e.errors()[0]["msg"] == f"Value error, Invalid email format. {email}"


# ADD tests ====================================================================


def test_add_contact(thing):
    payload = {
        "name": "Test Contact 2",
        "role": "Owner",
        "thing_id": thing.id,
        "emails": [{"email": "testcontact2@gmail.com", "email_type": "Primary"}],
        "phones": [{"phone_number": "+14153334444", "phone_type": "Primary"}],
        "addresses": [
            {
                "address_line_1": "123 Default St",
                "address_line_2": "Apt 8R",
                "city": "Test Metropolis",
                "state": "NM",
                "postal_code": "87501",
                "country": "United States",
                "address_type": "Primary",
            }
        ],
    }
    response = client.post("/contact", json=payload)
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert data["name"] == payload["name"]
    assert data["role"] == payload["role"]

    assert len(data["emails"]) == 1
    assert data["emails"][0]["contact_id"] == data["id"]
    assert data["emails"][0]["email"] == payload["emails"][0]["email"]
    assert data["emails"][0]["email_type"] == payload["emails"][0]["email_type"]

    assert len(data["phones"]) == 1
    assert data["phones"][0]["contact_id"] == data["id"]
    assert data["phones"][0]["phone_number"] == payload["phones"][0]["phone_number"]
    assert data["phones"][0]["phone_type"] == payload["phones"][0]["phone_type"]

    assert len(data["addresses"]) == 1
    assert data["addresses"][0]["contact_id"] == data["id"]
    assert (
        data["addresses"][0]["address_line_1"]
        == payload["addresses"][0]["address_line_1"]
    )
    assert (
        data["addresses"][0]["address_line_2"]
        == payload["addresses"][0]["address_line_2"]
    )
    assert data["addresses"][0]["city"] == payload["addresses"][0]["city"]
    assert data["addresses"][0]["state"] == payload["addresses"][0]["state"]
    assert data["addresses"][0]["postal_code"] == payload["addresses"][0]["postal_code"]
    assert data["addresses"][0]["country"] == payload["addresses"][0]["country"]
    assert (
        data["addresses"][0]["address_type"] == payload["addresses"][0]["address_type"]
    )

    cleanup_post_test(Contact, data["id"])


def test_add_address(contact):
    payload = {
        "address_line_1": "456 Secondary St",
        "address_line_2": "Apt 12A",
        "city": "Test Metropolis",
        "state": "NM",
        "postal_code": "87502",
        "country": "United States",
        "address_type": "Primary",
    }
    response = client.post(f"/contact/{contact.id}/address", json=payload)
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert data["contact_id"] == contact.id
    assert data["address_line_1"] == payload["address_line_1"]
    assert data["address_line_2"] == payload["address_line_2"]
    assert data["city"] == payload["city"]
    assert data["state"] == payload["state"]
    assert data["postal_code"] == payload["postal_code"]
    assert data["country"] == payload["country"]
    assert data["address_type"] == payload["address_type"]

    cleanup_post_test(Address, data["id"])


def test_add_address_404_contact_not_found(contact):
    bad_contact_id = 9999
    payload = {
        "address_line_1": "456 Secondary St",
        "address_line_2": "Apt 12A",
        "city": "Test Metropolis",
        "state": "NM",
        "postal_code": "87502",
        "country": "United States",
        "address_type": "Secondary",
    }
    response = client.post(f"/contact/{bad_contact_id}/address", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_add_email(contact):
    payload = {"email": "anothertestemail@nmt.edu", "email_type": "Primary"}
    response = client.post(f"/contact/{contact.id}/email", json=payload)
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert data["contact_id"] == contact.id
    assert data["email"] == payload["email"]
    assert data["email_type"] == payload["email_type"]

    cleanup_post_test(Email, data["id"])


def test_add_email_404_contact_not_found(contact):
    bad_contact_id = 9999
    payload = {"email": "anothertestemail@nmt.edu", "email_type": "Primary"}
    response = client.post(f"/contact/{bad_contact_id}/email", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_add_phone(contact):
    payload = {"phone_number": "+12345678901", "phone_type": "Primary"}
    response = client.post(f"/contact/{contact.id}/phone", json=payload)
    data = response.json()
    assert response.status_code == 201
    assert "id" in data
    assert data["contact_id"] == contact.id
    assert data["phone_number"] == payload["phone_number"]
    assert data["phone_type"] == payload["phone_type"]

    cleanup_post_test(Phone, data["id"])


def test_add_phone_404_contact_not_found(contact):
    bad_contact_id = 9999
    payload = {"phone_number": "+12345678901", "phone_type": "Primary"}
    response = client.post(f"/contact/{bad_contact_id}/phone", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


# GET tests ======================================================


def test_get_contacts(contact, email, address, phone):
    response = client.get("/contact")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == contact.id
    assert data["items"][0]["name"] == contact.name
    assert data["items"][0]["role"] == contact.role

    assert len(data["items"][0]["emails"]) == 1
    assert data["items"][0]["emails"][0]["id"] == email.id
    assert data["items"][0]["emails"][0]["contact_id"] == email.contact_id
    assert data["items"][0]["emails"][0]["email"] == email.email
    assert data["items"][0]["emails"][0]["email_type"] == email.email_type

    assert len(data["items"][0]["phones"]) == 1
    assert data["items"][0]["phones"][0]["id"] == phone.id
    assert data["items"][0]["phones"][0]["contact_id"] == phone.contact_id
    assert data["items"][0]["phones"][0]["phone_number"] == phone.phone_number
    assert data["items"][0]["phones"][0]["phone_type"] == phone.phone_type

    assert len(data["items"][0]["addresses"]) == 1
    assert data["items"][0]["addresses"][0]["id"] == address.id
    assert data["items"][0]["addresses"][0]["contact_id"] == address.contact_id
    assert data["items"][0]["addresses"][0]["address_line_1"] == address.address_line_1
    assert data["items"][0]["addresses"][0]["address_line_2"] == address.address_line_2
    assert data["items"][0]["addresses"][0]["city"] == address.city
    assert data["items"][0]["addresses"][0]["state"] == address.state
    assert data["items"][0]["addresses"][0]["postal_code"] == address.postal_code
    assert data["items"][0]["addresses"][0]["country"] == address.country
    assert data["items"][0]["addresses"][0]["address_type"] == address.address_type


def test_get_contact_by_id(contact, email, address, phone):
    response = client.get(f"/contact/{contact.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == contact.id
    assert data["name"] == contact.name
    assert data["role"] == contact.role

    assert len(data["emails"]) == 1
    assert data["emails"][0]["id"] == email.id
    assert data["emails"][0]["contact_id"] == email.contact_id
    assert data["emails"][0]["email"] == email.email
    assert data["emails"][0]["email_type"] == email.email_type

    assert len(data["phones"]) == 1
    assert data["phones"][0]["id"] == phone.id
    assert data["phones"][0]["contact_id"] == phone.contact_id
    assert data["phones"][0]["phone_number"] == phone.phone_number
    assert data["phones"][0]["phone_type"] == phone.phone_type

    assert len(data["addresses"]) == 1
    assert data["addresses"][0]["id"] == address.id
    assert data["addresses"][0]["contact_id"] == address.contact_id
    assert data["addresses"][0]["address_line_1"] == address.address_line_1
    assert data["addresses"][0]["address_line_2"] == address.address_line_2
    assert data["addresses"][0]["city"] == address.city
    assert data["addresses"][0]["state"] == address.state
    assert data["addresses"][0]["postal_code"] == address.postal_code
    assert data["addresses"][0]["country"] == address.country
    assert data["addresses"][0]["address_type"] == address.address_type


def test_get_contact_by_id_404_not_found(contact):
    bad_contact_id = 99999
    response = client.get(f"/contact/{bad_contact_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_get_contact_emails(contact, email):
    response = client.get(f"/contact/{contact.id}/email")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == email.id
    assert data["items"][0]["contact_id"] == email.contact_id
    assert data["items"][0]["email"] == email.email
    assert data["items"][0]["email_type"] == email.email_type


def test_get_contact_emails_404_contact_not_found(contact, email):
    bad_contact_id = 99999
    response = client.get(f"/contact/{bad_contact_id}/email")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_get_contact_phones(contact, phone):
    response = client.get(f"/contact/{contact.id}/phone")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == phone.id
    assert data["items"][0]["contact_id"] == phone.contact_id
    assert data["items"][0]["phone_number"] == phone.phone_number
    assert data["items"][0]["phone_type"] == phone.phone_type


def test_get_contact_phones_404_contact_not_found(contact, phone):
    bad_contact_id = 99999
    response = client.get(f"/contact/{bad_contact_id}/phone")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_get_contact_addresses(contact, address):
    response = client.get(f"/contact/{contact.id}/address")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == address.id
    assert data["items"][0]["contact_id"] == address.contact_id
    assert data["items"][0]["address_line_1"] == address.address_line_1
    assert data["items"][0]["address_line_2"] == address.address_line_2
    assert data["items"][0]["city"] == address.city
    assert data["items"][0]["state"] == address.state
    assert data["items"][0]["postal_code"] == address.postal_code
    assert data["items"][0]["country"] == address.country
    assert data["items"][0]["address_type"] == address.address_type


def test_get_contact_addresses_404_contact_not_found(contact, address):
    bad_contact_id = 99999
    response = client.get(f"/contact/{bad_contact_id}/address")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_get_emails(email):
    response = client.get("/contact/email")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == email.id
    assert data["items"][0]["contact_id"] == email.contact_id
    assert data["items"][0]["email"] == email.email
    assert data["items"][0]["email_type"] == email.email_type


def test_get_email_by_id(email):
    response = client.get(f"/contact/email/{email.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == email.id
    assert data["contact_id"] == email.contact_id
    assert data["email"] == email.email
    assert data["email_type"] == email.email_type


def test_get_email_404_not_found(email):
    bad_email_id = 99999
    response = client.get(f"/contact/email/{bad_email_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Email with ID {bad_email_id} not found."


def test_get_phones(phone):
    response = client.get("/contact/phone")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == phone.id
    assert data["items"][0]["contact_id"] == phone.contact_id
    assert data["items"][0]["phone_number"] == phone.phone_number
    assert data["items"][0]["phone_type"] == phone.phone_type


def test_get_phone_by_id(phone):
    response = client.get(f"/contact/phone/{phone.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == phone.id
    assert data["contact_id"] == phone.contact_id
    assert data["phone_number"] == phone.phone_number
    assert data["phone_type"] == phone.phone_type


def test_get_addresses(address):
    response = client.get("/contact/address")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == address.id
    assert data["items"][0]["contact_id"] == address.contact_id
    assert data["items"][0]["address_line_1"] == address.address_line_1
    assert data["items"][0]["address_line_2"] == address.address_line_2
    assert data["items"][0]["city"] == address.city
    assert data["items"][0]["state"] == address.state
    assert data["items"][0]["postal_code"] == address.postal_code
    assert data["items"][0]["country"] == address.country
    assert data["items"][0]["address_type"] == address.address_type


def test_get_address_by_id(address):
    response = client.get(f"/contact/address/{address.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == address.id
    assert data["contact_id"] == address.contact_id
    assert data["address_line_1"] == address.address_line_1
    assert data["address_line_2"] == address.address_line_2
    assert data["city"] == address.city
    assert data["state"] == address.state
    assert data["postal_code"] == address.postal_code
    assert data["country"] == address.country
    assert data["address_type"] == address.address_type


def test_get_address_by_id_404_not_found(address):
    bad_address_id = 99999
    response = client.get(f"/contact/address/{bad_address_id}")
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Address with ID {bad_address_id} not found."


def test_get_thing_contact_associations(thing_contact_association):
    response = client.get("/contact/thing-association")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == thing_contact_association.id
    assert data["items"][0]["contact_id"] == thing_contact_association.contact_id
    assert data["items"][0]["thing_id"] == thing_contact_association.thing_id


def test_get_contact_thing_contact_association(contact, thing_contact_association):
    response = client.get(f"/contact/{contact.id}/thing-association")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == thing_contact_association.id
    assert data["items"][0]["contact_id"] == thing_contact_association.contact_id
    assert data["items"][0]["thing_id"] == thing_contact_association.thing_id


def test_get_thing_contact_association_404_contact_not_found(
    contact, thing_contact_association
):
    bad_contact_id = 999999
    response = client.get(f"/contact/{bad_contact_id}/thing-association")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_get_thing_contact_association_by_id(thing_contact_association):
    response = client.get(f"/contact/thing-association/{thing_contact_association.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == thing_contact_association.id
    assert data["contact_id"] == thing_contact_association.contact_id
    assert data["thing_id"] == thing_contact_association.thing_id


def test_get_thing_contact_association_by_id_404_not_found(thing_contact_association):
    bad_id = 999999
    response = client.get(f"/contact/thing-association/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"ThingContactAssociation with ID {bad_id} not found."


# PATCH tests ==================================================================


def test_patch_contact(contact):
    payload = {"name": "Updated Contact"}
    response = client.patch(
        f"/contact/{contact.id}",
        json=payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == contact.id
    assert data["name"] == payload["name"]

    cleanup_patch_test(Contact, payload, contact)


def test_patch_contact_404_not_found(contact):
    bad_contact_id = 999999
    payload = {"name": "Updated Contact"}
    response = client.patch(
        f"/contact/{bad_contact_id}",
        json=payload,
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_patch_email(email):
    payload = {"email": "boo@bar.com"}
    response = client.patch(f"/contact/email/{email.id}", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == email.id
    assert data["contact_id"] == email.contact_id
    assert data["email"] == payload["email"]
    assert data["email_type"] == email.email_type

    cleanup_patch_test(Email, payload, email)


def test_patch_email_404_not_found(email):
    bad_email_id = 999999
    payload = {"email": "boo@bar.com"}
    response = client.patch(f"/contact/email/{bad_email_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Email with ID {bad_email_id} not found."


def test_patch_phone(phone):
    payload = {"phone_number": "+19709654321"}
    response = client.patch(f"/contact/phone/{phone.id}", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == phone.id
    assert data["contact_id"] == phone.contact_id
    assert data["phone_number"] == payload["phone_number"]
    assert data["phone_type"] == phone.phone_type

    cleanup_patch_test(Phone, payload, phone)


def test_patch_phone_404_not_found(phone):
    bad_phone_id = 999999
    payload = {"phone_number": "+19709654321"}
    response = client.patch(f"/contact/phone/{bad_phone_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Phone with ID {bad_phone_id} not found."


def test_edit_address(address):
    payload = {
        "address_line_1": "456 Elm St",
        "address_line_2": "Apt 21B",
        "city": "Updated City",
        "state": "CA",
        "postal_code": "90210",
        "country": "United States",
    }
    response = client.patch(f"/contact/address/{address.id}", json=payload)
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == address.id
    assert data["contact_id"] == address.contact_id
    assert data["address_line_1"] == payload["address_line_1"]
    assert data["address_line_2"] == payload["address_line_2"]
    assert data["city"] == payload["city"]
    assert data["state"] == payload["state"]
    assert data["postal_code"] == payload["postal_code"]
    assert data["country"] == payload["country"]
    assert data["address_type"] == address.address_type

    cleanup_patch_test(Address, payload, address)


def test_patch_address_404_not_found(address):
    bad_address_id = 999999
    payload = {
        "address_line_1": "456 Elm St",
        "address_line_2": "Apt 21B",
        "city": "Updated City",
        "state": "CA",
        "postal_code": "90210",
        "country": "United States",
    }
    response = client.patch(f"/contact/address/{bad_address_id}", json=payload)
    data = response.json()
    assert response.status_code == 404
    assert data["detail"] == f"Address with ID {bad_address_id} not found."


# DELETE tests =================================================================


def test_delete_contact(second_contact, second_email, second_phone, second_address):
    response = client.delete(f"/contact/{second_contact.id}")
    assert response.status_code == 204

    # verify contact is deleted and it cascades to emails, phones, and addresses
    response = client.get(f"/contact/{second_contact.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {second_contact.id} not found."

    response = client.get(f"/contact/email/{second_email.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Email with ID {second_email.id} not found."

    response = client.get(f"/contact/phone/{second_phone.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Phone with ID {second_phone.id} not found."

    response = client.get(f"/contact/address/{second_address.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Address with ID {second_address.id} not found."


def test_delete_contact_404_not_found(second_contact):
    bad_contact_id = 999999
    response = client.delete(f"/contact/{bad_contact_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Contact with ID {bad_contact_id} not found."


def test_delete_email(second_contact, second_email):
    response = client.delete(f"/contact/email/{second_email.id}")
    assert response.status_code == 204

    # verify email is deleted
    response = client.get(f"/contact/email/{second_email.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Email with ID {second_email.id} not found."

    # verify email is no longer associated with the contact
    response = client.get(f"/contact/{second_contact.id}")
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert data["emails"] == []


def test_delete_email_404_not_found(second_email):
    bad_email_id = 999999
    response = client.delete(f"/contact/email/{bad_email_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Email with ID {bad_email_id} not found."


def test_delete_phone(second_contact, second_phone):
    response = client.delete(f"/contact/phone/{second_phone.id}")
    assert response.status_code == 204

    # verify phone is deleted
    response = client.get(f"/contact/phone/{second_phone.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Phone with ID {second_phone.id} not found."

    # verify phone is no longer associated with the contact
    response = client.get(f"/contact/{second_contact.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["phones"] == []


def test_delete_phone_404_not_found(second_phone):
    bad_phone_id = 999999
    response = client.delete(f"/contact/phone/{bad_phone_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Phone with ID {bad_phone_id} not found."


def test_delete_address(second_contact, second_address):
    response = client.delete(f"/contact/address/{second_address.id}")
    assert response.status_code == 204

    # verify address is deleted
    response = client.get(f"/contact/address/{second_address.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Address with ID {second_address.id} not found."

    # verify address is no longer associated with the contact
    response = client.get(f"/contact/{second_contact.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["addresses"] == []


def test_delete_address_404_not_found(second_address):
    bad_address_id = 99999
    response = client.delete(f"/contact/address/{bad_address_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Address with ID {bad_address_id} not found."
