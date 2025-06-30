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
from services.validation import get_category
from tests import client


def test_add_lexicon_category():
    name = "Test Category"
    description = "This is a test category."

    response = client.post(
        "/lexicon/category/add",
        json={"name": name, "description": description},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == name
    assert data["description"] == description


def test_add_lexicon_term():
    term = "test_term"
    definition = "This is a test definition."
    category = "Test Category"

    response = client.post(
        "/lexicon/add",
        json={"term": term, "definition": definition, "category": category},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["term"] == term
    assert data["definition"] == definition


def test_get_category():
    items = get_category("casing_material")
    assert isinstance(items, list)


def test_add_triple():
    subject = {
        "term": "MG-030",
        "definition": "magdalena well",
        "category": "location_identifier",
    }
    predicate = "same_as"
    object_ = {
        "term": "USGS1234",
        "definition": "magdalena well",
        "category": "location_identifier",
    }

    response = client.post(
        "/lexicon/triple/add",
        json={
            "subject": subject,
            "predicate": predicate,
            "object_": object_,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == subject["term"]
    assert data["predicate"] == predicate
    assert data["object_"] == object_["term"]


# ============= EOF =============================================
