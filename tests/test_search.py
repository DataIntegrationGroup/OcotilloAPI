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
from sqlalchemy import select

from db import search
from db.contact import Contact, Phone, Email
from db.engine import session_ctx
from tests import client


def test_search_api(thing, sample):
    response = client.get("/search", params={"q": "Test"})
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    items = data.get("items")
    assert isinstance(items, list)
    assert len(items) == 1


@pytest.mark.skip(reason="This test is not working .")
def test_search_api2():
    response = client.get("/search", params={"q": "riochama"})
    assert response.status_code == 200
    data = response.json()
    print(data)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["label"] == "riochama.png"


def test_search_api3():
    response = client.get("/search", params={"q": "nonexistent"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    items = data.get("items")
    assert isinstance(items, list)
    assert len(items) == 0


def test_search_contact(contact):
    with session_ctx() as session:
        query = search(select(Contact), "Test")

        queried_contact = session.scalars(query).first()
        assert queried_contact is not None


def test_search_contact_no_results(contact):
    with session_ctx() as session:
        query = search(select(Contact), "NonExistent")
        queried_contact = session.scalars(query).first()
        assert queried_contact is None


def test_search_contact_like(contact):
    with session_ctx() as session:
        query = search(select(Contact), "Te")
        queried_contact = session.scalars(query).first()
        assert queried_contact is not None


def test_search_contact_by_email(contact, email):
    with session_ctx() as session:
        vector = Contact.search_vector | Email.search_vector
        query = search(
            select(Contact).join(Email),
            "test@example.com",
            vector=vector,
        )

        queried_contact = session.scalars(query).first()
        assert queried_contact is not None


def test_search_contact_by_email_no_results(contact, email):
    with session_ctx() as session:
        vector = Contact.search_vector | Email.search_vector
        query = search(
            select(Contact).join(Email),
            "foo",
            vector=vector,
        )
        queried_contact = session.scalars(query).first()
        assert queried_contact is None


def test_search_contact_by_phone_number(contact, phone):
    with session_ctx() as session:
        vector = Contact.search_vector | Phone.search_vector
        query = search(
            select(Contact).join(Phone),
            "+15051234567",
            vector=vector,
        )
        queried_contact = session.scalars(query).first()
        assert queried_contact is not None


def test_search_contact_by_phone_number_no_results(contact, phone):
    with session_ctx() as session:
        vector = Contact.search_vector | Phone.search_vector
        query = search(
            select(Contact).join(Phone),
            "+12345678902",
            vector=vector,
        )
        queried_contact = session.scalars(query).first()
        assert queried_contact is None


def test_search_contact_by_phone_like(contact, phone):
    with session_ctx() as session:
        vector = Contact.search_vector | Phone.search_vector
        query = search(
            select(Contact).join(Phone),
            "+15",
            vector=vector,
        )
        queried_contact = session.scalars(query).first()
        assert queried_contact is not None


def test_search_contact_by_phone_like_no_results(contact, phone):
    with session_ctx() as session:
        vector = Contact.search_vector | Phone.search_vector
        query = search(
            select(Contact).join(Phone),
            "+99",
            vector=vector,
        )
        queried_contact = session.scalars(query).first()
        assert queried_contact is None


# def test_search_owner_by_contact_name():
#     session = next(get_db_session())
#
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "Test Contact",
#         vector=vector,
#     )
#     owner = session.scalars(query).first()
#     assert owner is not None
#     session.close()
#
#
# def test_search_owner_by_contact_name_no_results():
#     session = next(get_db_session())
#
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "NonExistentContact",
#         vector=vector,
#     )
#     owner = session.scalars(query).first()
#     assert owner is None
#     session.close()
#
#
# def test_search_owner_by_contact_phonenumber():
#     session = next(get_db_session())
#
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "+12345678901",
#         vector=vector,
#     )
#     contact = session.scalars(query).first()
#     assert contact is not None
#     session.close()
#
#
# def test_search_owner_by_contact_phonenumber_no_results():
#     session = next(get_db_session())
#
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "NonExistentPhoneNumber",
#         vector=vector,
#     )
#     contact = session.scalars(query).first()
#     assert contact is None
#     session.close()
#
#
# def test_search_owner_by_phonelike():
#     session = next(get_db_session())
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "+12%",
#         vector=vector,
#     )
#     contact = session.scalars(query).first()
#     assert contact is not None
#     session.close()
#
#
# def test_search_owner_by_phonelike_no_results():
#     session = next(get_db_session())
#     vector = Contact.search_vector
#     query = search(
#         select(Owner).join(OwnerContactAssociation).join(Contact),
#         "NonExistentPhone%",
#         vector=vector,
#     )
#     contact = session.scalars(query).first()
#     assert contact is None
#     session.close()


# API ===========================================================
# def test_search_owner_by_contact_name_api():
#     response = client.get("/base/owner", params={"search": '"Contact X"'})
#     assert response.status_code == 200
#     data = response.json()
#     assert len(data) == 1
#     assert data[0]["name"] == "Test Owner 1"


# ============= EOF =============================================
