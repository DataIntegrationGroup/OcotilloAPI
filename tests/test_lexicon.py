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
from datetime import timezone

import pytest

from core.dependencies import (
    viewer_function,
    lexicon_admin_function,
    lexicon_editor_function,
)
from db import LexiconTerm, LexiconCategory, LexiconTriple
from main import app
from tests import (
    client,
    override_authentication,
    cleanup_post_test,
    cleanup_patch_test,
    DT_FMT,
)


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():

    app.dependency_overrides[viewer_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )

    app.dependency_overrides[lexicon_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[lexicon_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


# POST tests ===================================================================


@pytest.mark.skip(reason="This is deprecated functionality. Category must exist")
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

    cleanup_post_test(LexiconTerm, data["id"])
    cleanup_post_test(LexiconCategory, data["categories"][0]["id"])


def test_add_lexicon_term_with_existing_categories():
    payload = {
        "term": "test_term_existing_categories",
        "definition": "This is a test definition.",
        # if the category already exists, and the name is a pk, why would you have to provide the description?
        # "categories": ["name": "unit", "description": None}],
        "categories": ["unit"],
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
    assert data["categories"][0]["name"] == payload["categories"][0]

    cleanup_post_test(LexiconTerm, data["id"])


def test_add_lexicon_category():
    payload = {"name": "test category name", "description": "test category description"}
    response = client.post("/lexicon/category", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]

    cleanup_post_test(LexiconCategory, data["id"])


@pytest.mark.skip(
    reason="Lexicon triple is not used and should be deprecated/removed if its not going to be used"
)
def test_add_lexicon_triple_new_terms():
    subject = {
        "term": "MG-030",
        "definition": "magdalena well",
        "categories": [{"name": "location_identifier"}],
    }
    predicate = "same_as"
    object_ = {
        "term": "USGS1234",
        "definition": "magdalena well",
        "categories": [{"name": "location_identifier"}],
    }
    payload = {
        "subject": subject,
        "predicate": predicate,
        "object_": object_,
    }

    response = client.post("/lexicon/triple", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["subject"] == subject["term"]
    assert data["predicate"] == predicate
    assert data["object_"] == object_["term"]

    cleanup_post_test(LexiconTriple, data["id"])

    response = client.get(f"/lexicon/term?term={subject['term']}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["term"] == subject["term"]
    assert data["items"][0]["definition"] == subject["definition"]

    cleanup_post_test(LexiconTerm, data["items"][0]["id"])

    response = client.get(f"/lexicon/term?term={object_['term']}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["term"] == object_["term"]
    assert data["items"][0]["definition"] == object_["definition"]

    cleanup_post_test(LexiconTerm, data["items"][0]["id"])
    cleanup_post_test(LexiconCategory, data["items"][0]["categories"][0]["id"])


@pytest.mark.skip(
    reason="Lexicon triple is not used and should be deprecated/removed if its not going to be used"
)
def test_add_lexicon_triple_existing_terms(lexicon_term, second_lexicon_term):
    subject = {
        "term": lexicon_term.term,
        "definition": lexicon_term.definition,
        "categories": [
            {
                "name": category.name,
                "description": category.description,
            }
            for category in lexicon_term.categories
        ],
    }
    predicate = "same_as"
    object_ = {
        "term": second_lexicon_term.term,
        "definition": second_lexicon_term.definition,
        "categories": [
            {
                "name": category.name,
                "description": category.description,
            }
            for category in second_lexicon_term.categories
        ],
    }
    payload = {
        "subject": subject,
        "predicate": predicate,
        "object_": object_,
    }

    response = client.post("/lexicon/triple", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data
    assert data["subject"] == subject["term"]
    assert data["predicate"] == predicate
    assert data["object_"] == object_["term"]

    cleanup_post_test(LexiconTriple, data["id"])


# PATCH tests ==================================================================


def test_patch_term(lexicon_term):
    payload = {"term": "patched term", "definition": "patched definition"}
    response = client.patch(f"/lexicon/term/{lexicon_term.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["term"] == payload["term"]
    assert data["definition"] == payload["definition"]

    cleanup_patch_test(LexiconTerm, payload, lexicon_term)


def test_patch_term_404_not_found(lexicon_term):
    bad_id = 99999
    payload = {"term": "patched term", "definition": "patched definition"}
    response = client.patch(f"/lexicon/term/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTerm with ID {bad_id} not found."


def test_patch_category(lexicon_category):
    payload = {"name": "patched name", "description": "patched description"}
    response = client.patch(f"/lexicon/category/{lexicon_category.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]

    cleanup_patch_test(LexiconCategory, payload, lexicon_category)


def test_patch_category_404_not_found(lexicon_category):
    bad_id = 99999
    payload = {"name": "patched name", "definition": "patched definition"}
    response = client.patch(f"/lexicon/category/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconCategory with ID {bad_id} not found."


def test_patch_triple(lexicon_triple, third_lexicon_term, fourth_lexicon_term):
    payload = {
        "subject": third_lexicon_term.term,
        "predicate": "patched predicate",
        "object_": fourth_lexicon_term.term,
    }
    response = client.patch(f"/lexicon/triple/{lexicon_triple.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["subject"] == payload["subject"]
    assert data["predicate"] == payload["predicate"]
    assert data["object_"] == payload["object_"]

    cleanup_patch_test(LexiconTriple, payload, lexicon_triple)


def test_patch_triple_404_not_found(
    lexicon_triple, third_lexicon_term, fourth_lexicon_term
):
    bad_id = 99999
    payload = {
        "subject": third_lexicon_term.term,
        "predicate": "patched predicate",
        "object_": fourth_lexicon_term.term,
    }
    response = client.patch(f"/lexicon/triple/{bad_id}", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTriple with ID {bad_id} not found."


def test_patch_triple_409_bad_subject(lexicon_triple, third_lexicon_term):
    bad_subject = "nonexistent subject"
    payload = {
        "subject": bad_subject,
        "predicate": "patched predicate",
        "object_": third_lexicon_term.term,
    }
    response = client.patch(f"/lexicon/triple/{lexicon_triple.id}", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "subject"]
    assert data["detail"][0]["msg"] == f"LexiconTerm with term {bad_subject} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"subject": bad_subject}


def test_patch_triple_409_bad_object(lexicon_triple, third_lexicon_term):
    bad_object = "nonexistent object"
    payload = {
        "subject": third_lexicon_term.term,
        "predicate": "patched predicate",
        "object_": bad_object,
    }
    response = client.patch(f"/lexicon/triple/{lexicon_triple.id}", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert data["detail"][0]["loc"] == ["body", "object_"]
    assert data["detail"][0]["msg"] == f"LexiconTerm with term {bad_object} not found."
    assert data["detail"][0]["type"] == "value_error"
    assert data["detail"][0]["input"] == {"object_": bad_object}


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
    assert data["created_at"] == lexicon_term.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["term"] == lexicon_term.term
    assert data["definition"] == lexicon_term.definition
    assert len(data["categories"]) == 1
    assert data["categories"][0]["id"] == lexicon_term.categories[0].id
    assert data["categories"][0]["created_at"] == lexicon_term.categories[
        0
    ].created_at.astimezone(timezone.utc).strftime(DT_FMT)
    assert data["categories"][0]["name"] == lexicon_term.categories[0].name
    assert (
        data["categories"][0]["description"] == lexicon_term.categories[0].description
    )


def test_get_lexicon_terms_sort_categories_branch():
    """
    Ensure the special-case branch (sort == 'categories') in GET /lexicon is exercised.
    It should not apply sorting/filtering and still return a valid pagination payload.
    """
    resp = client.get("/lexicon/term", params={"sort": "categories"})
    assert resp.status_code == 200
    data = resp.json()
    # fastapi-pagination returns a Page-like object with these keys
    assert "items" in data
    assert "total" in data


def test_get_lexicon_term_by_id_404_not_found(lexicon_term):
    bad_id = 999999
    response = client.get(f"/lexicon/term/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTerm with ID {bad_id} not found."


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
    assert data["created_at"] == lexicon_category.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["name"] == lexicon_category.name
    assert data["description"] == lexicon_category.description


def test_get_lexicon_category_by_id_404_not_found(lexicon_category):
    bad_id = 999999
    response = client.get(f"/lexicon/category/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconCategory with ID {bad_id} not found."


def test_get_lexicon_triples(lexicon_triple):
    response = client.get("/lexicon/triple")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["items"][0]["id"] == lexicon_triple.id
    assert data["items"][0]["created_at"] == lexicon_triple.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["items"][0]["subject"] == lexicon_triple.subject
    assert data["items"][0]["predicate"] == lexicon_triple.predicate
    assert data["items"][0]["object_"] == lexicon_triple.object_


def test_get_lexicon_triple_by_id(lexicon_triple):
    response = client.get(f"/lexicon/triple/{lexicon_triple.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == lexicon_triple.id
    assert data["created_at"] == lexicon_triple.created_at.astimezone(
        timezone.utc
    ).strftime(DT_FMT)
    assert data["subject"] == lexicon_triple.subject
    assert data["predicate"] == lexicon_triple.predicate
    assert data["object_"] == lexicon_triple.object_


def test_get_lexicon_triple_by_id_404_not_found(lexicon_triple):
    bad_id = 999999
    response = client.get(f"/lexicon/triple/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTriple with ID {bad_id} not found."


# DELETE tests =================================================================


def test_delete_lexicon_term(second_lexicon_term):
    response = client.delete(f"/lexicon/term/{second_lexicon_term.id}")
    assert response.status_code == 204

    # verify the lexicon term was deleted
    response = client.get(f"/lexicon/term/{second_lexicon_term.id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTerm with ID {second_lexicon_term.id} not found."


def test_delete_lexicon_term_404_not_found(second_lexicon_term):
    bad_id = 999999
    response = client.delete(f"/lexicon/term/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTerm with ID {bad_id} not found."


def test_delete_lexicon_category(second_lexicon_category):
    response = client.delete(f"/lexicon/category/{second_lexicon_category.id}")
    assert response.status_code == 204

    # verify the lexicon category was deleted
    response = client.get(f"/lexicon/category/{second_lexicon_category.id}")
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"]
        == f"LexiconCategory with ID {second_lexicon_category.id} not found."
    )


def test_delete_lexicon_category_404_not_found(second_lexicon_category):
    bad_id = 999999
    response = client.delete(f"/lexicon/category/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconCategory with ID {bad_id} not found."


def test_delete_lexicon_triple(second_lexicon_triple):
    response = client.delete(f"/lexicon/triple/{second_lexicon_triple.id}")
    assert response.status_code == 204

    # verify the lexicon triple was deleted
    response = client.get(f"/lexicon/triple/{second_lexicon_triple.id}")
    assert response.status_code == 404
    data = response.json()
    assert (
        data["detail"] == f"LexiconTriple with ID {second_lexicon_triple.id} not found."
    )


def test_delete_lexicon_triple_404_not_found(second_lexicon_triple):
    bad_id = 999999
    response = client.delete(f"/lexicon/triple/{bad_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == f"LexiconTriple with ID {bad_id} not found."
