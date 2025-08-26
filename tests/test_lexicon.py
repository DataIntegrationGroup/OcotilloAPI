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
from db import Lexicon, Category
from tests import client, override_authentication, cleanup_post_test, cleanup_patch_test

from core.dependencies import admin_function, viewer_function, editor_function
from main import app

import pytest


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


# POST tests ===================================================================


def test_add_lexicon_term_with_new_categories():
    payload = {
        "term": "test_term",
        "definition": "This is a test definition.",
        "categories": [{"name": "test category", "description": "test lexicon terms"}],
    }
    response = client.post(
        "/lexicon/term",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["term"] == payload["term"]
    assert data["definition"] == payload["definition"]
    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == payload["categories"][0]["name"]
    assert (
        data["categories"][0]["description"] == payload["categories"][0]["description"]
    )

    cleanup_post_test(Lexicon, data["id"])
    cleanup_post_test(Category, data["categories"][0]["id"])


def test_add_lexicon_term_with_existing_categories():
    payload = {
        "term": "test_term_existing_categories",
        "definition": "This is a test definition.",
        "categories": [{"name": "unit", "description": None}],
    }
    response = client.post(
        "/lexicon/term",
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["term"] == payload["term"]
    assert data["definition"] == payload["definition"]
    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == payload["categories"][0]["name"]
    assert (
        data["categories"][0]["description"] == payload["categories"][0]["description"]
    )

    cleanup_post_test(Lexicon, data["id"])


# TODO: this should raise an error since each term MUST be associated with a category
def test_add_lexicon_term_with_no_categories():
    payload = {
        "term": "test_term_no_categories",
        "definition": "This is a test definition without categories.",
        "categories": None,
    }
    response = client.post(
        "/lexicon/term",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["term"] == payload["term"]
    assert data["definition"] == payload["definition"]
    assert data["categories"] == []

    cleanup_post_test(Lexicon, data["id"])


def test_add_lexicon_category():
    payload = {"name": "test category name", "description": "test category description"}
    response = client.post("/lexicon/category", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]

    cleanup_post_test(Category, data["id"])


# def test_add_triple():
#     subject = {
#         "term": "MG-030",
#         "definition": "magdalena well",
#         "category": "location_identifier",
#     }
#     predicate = "same_as"
#     object_ = {
#         "term": "USGS1234",
#         "definition": "magdalena well",
#         "category": "location_identifier",
#     }

#     response = client.post(
#         "/lexicon/triple/add",
#         json={
#             "subject": subject,
#             "predicate": predicate,
#             "object_": object_,
#         },
#     )

#     assert response.status_code == 201
#     data = response.json()
#     assert data["subject"] == subject["term"]
#     assert data["predicate"] == predicate
#     assert data["object_"] == object_["term"]


# PATCH tests ==================================================================


def test_patch_term(lexicon_term):
    payload = {"term": "patched term", "definition": "patched definition"}
    response = client.patch(f"/lexicon/term/{lexicon_term.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["term"] == payload["term"]
    assert data["definition"] == payload["definition"]

    cleanup_patch_test(Lexicon, payload, lexicon_term)


def test_patch_term_404_not_found(lexicon_term):
    bad_id = 99999
    payload = {"term": "patched term", "definition": "patched definition"}
    response = client.patch(f"/lexicon/term/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Lexicon with ID {bad_id} not found."


def test_patch_category(lexicon_category):
    payload = {"name": "patched name", "description": "patched description"}
    response = client.patch(f"/lexicon/category/{lexicon_category.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]

    cleanup_patch_test(Category, payload, lexicon_category)


def test_patch_category_404_not_found(lexicon_category):
    bad_id = 99999
    payload = {"name": "patched name", "definition": "patched definition"}
    response = client.patch(f"/lexicon/category/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Category with ID {bad_id} not found."


# GET tests ====================================================================


def test_get_lexicon_terms():
    # many terms are defined in conftest.py and core/lexicon.json, so rather
    # than test a specific one just ensure the responses are correct
    response = client.get("lexicon/term")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for term in data["items"]:
        assert isinstance(term["id"], int)
        assert isinstance(term["created_at"], str)
        assert isinstance(term["term"], str)
        assert isinstance(term["definition"], str)
        assert isinstance(term["categories"], list)


def test_get_lexicon_term_by_id(lexicon_term):
    response = client.get(f"/lexicon/term/{lexicon_term.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lexicon_term.id
    assert data["created_at"] == lexicon_term.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["term"] == lexicon_term.term
    assert data["definition"] == lexicon_term.definition
    assert len(data["categories"]) == 1
    assert data["categories"][0]["id"] == lexicon_term.categories[0].id
    assert data["categories"][0]["created_at"] == lexicon_term.categories[
        0
    ].created_at.isoformat().replace("+00:00", "Z")
    assert data["categories"][0]["name"] == lexicon_term.categories[0].name
    assert (
        data["categories"][0]["description"] == lexicon_term.categories[0].description
    )


def test_get_lexicon_term_by_id_404_not_found(lexicon_term):
    bad_id = 999999
    response = client.get(f"/lexicon/term/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Lexicon with ID {bad_id} not found."


def test_get_lexicon_categories():
    # many categories are defined in conftest.py and core/lexicon.json, so
    # rather than test a specific one just ensure the responses are correct
    response = client.get("/lexicon/category")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for category in data["items"]:
        assert isinstance(category["id"], int)
        assert isinstance(category["created_at"], str)
        assert isinstance(category["name"], str)
        assert isinstance(category["description"], (str, type(None)))


def test_get_lexicon_category_by_id(lexicon_category):
    response = client.get(f"/lexicon/category/{lexicon_category.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lexicon_category.id
    assert data["created_at"] == lexicon_category.created_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert data["name"] == lexicon_category.name
    assert data["description"] == lexicon_category.description


def test_get_lexicon_category_by_id_404_not_found(lexicon_category):
    bad_id = 999999
    response = client.get(f"/lexicon/category/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Category with ID {bad_id} not found."


# DELETE tests =================================================================


def test_delete_lexicon_term(second_lexicon_term):
    response = client.delete(f"/lexicon/term/{second_lexicon_term.id}")
    assert response.status_code == 204

    # verify the lexicon term was deleted
    response = client.get(f"/lexicon/term/{second_lexicon_term.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Lexicon with ID {second_lexicon_term.id} not found."


def test_delete_lexicon_term_404_not_found(second_lexicon_term):
    bad_id = 999999
    response = client.delete(f"/lexicon/term/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"Lexicon with ID {bad_id} not found."
