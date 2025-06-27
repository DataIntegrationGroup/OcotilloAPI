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
from sqlalchemy import select
from sqlalchemy_searchable import search

from db import database_sessionmaker
from db.base import Owner, Contact, OwnerContactAssociation


from tests import client


def test_search_query():
    session = database_sessionmaker()

    query = search(select(Owner), "Test")
    owner = session.scalars(query).first()
    assert owner is not None
    session.close()


def test_search_query_no_results():
    session = database_sessionmaker()

    query = search(select(Owner), "NonExistentOwner")
    owner = session.scalars(query).first()
    assert owner is None
    session.close()


def test_search_owner_by_contact_name():
    session = database_sessionmaker()

    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "Test Contact",
        vector=vector,
    )
    owner = session.scalars(query).first()
    assert owner is not None
    session.close()


def test_search_owner_by_contact_name_no_results():
    session = database_sessionmaker()

    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "NonExistentContact",
        vector=vector,
    )
    owner = session.scalars(query).first()
    assert owner is None
    session.close()


def test_search_owner_by_contact_phonenumber():
    session = database_sessionmaker()

    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "+12345678901",
        vector=vector,
    )
    contact = session.scalars(query).first()
    assert contact is not None
    session.close()


def test_search_owner_by_contact_phonenumber_no_results():
    session = database_sessionmaker()

    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "NonExistentPhoneNumber",
        vector=vector,
    )
    contact = session.scalars(query).first()
    assert contact is None
    session.close()


def test_search_owner_by_phonelike():
    session = database_sessionmaker()
    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "+12%",
        vector=vector,
    )
    contact = session.scalars(query).first()
    assert contact is not None
    session.close()


def test_search_owner_by_phonelike_no_results():
    session = database_sessionmaker()
    vector = Contact.search_vector
    query = search(
        select(Owner).join(OwnerContactAssociation).join(Contact),
        "NonExistentPhone%",
        vector=vector,
    )
    contact = session.scalars(query).first()
    assert contact is None
    session.close()


# API ===========================================================
def test_search_owner_by_contact_name_api():
    response = client.get("/base/owner", params={"search": '"Contact X"'})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Owner 1"

    # assert len(data["items"]) > 0
    # assert "Test Contact" in data["items"][0]["contacts"][0]["name"]


# ============= EOF =============================================
