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
import json

import pytest
from core.dependencies import (
    admin_function,
    amp_admin_function,
    amp_editor_function,
    amp_viewer_function,
    editor_function,
    viewer_function,
)
from main import app
from tests import client, override_authentication


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


def test_get_contacts_filter_things_contains(water_well_thing, contact):
    fl = json.dumps(
        {"field": "things", "operator": "contains", "value": "Well"},
    )
    response = client.get("/contact", params=[("filter", fl)])
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert contact.id in ids


def test_get_contacts_filter_things_contains_no_match(
    water_well_thing,
    contact,
):
    fl = json.dumps(
        {
            "field": "things",
            "operator": "contains",
            "value": "ZyxyzNoMatch999",
        }
    )
    response = client.get("/contact", params=[("filter", fl)])
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert contact.id not in ids


def test_get_contacts_filter_things_nnull(water_well_thing, contact):
    fl = json.dumps(
        {"field": "things", "operator": "nnull", "value": True},
    )
    response = client.get("/contact", params=[("filter", fl)])
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert contact.id in ids


def test_get_contacts_multiple_filters_and(water_well_thing, contact):
    fl_a = json.dumps(
        {"field": "things", "operator": "contains", "value": "Well"},
    )
    fl_b = json.dumps(
        {"field": "name", "operator": "contains", "value": "Test"},
    )
    response = client.get(
        "/contact",
        params=[("filter", fl_a), ("filter", fl_b)],
    )
    assert response.status_code == 200
    data = response.json()
    ids = [item["id"] for item in data["items"]]
    assert contact.id in ids


def test_get_contacts_sort_things_asc(water_well_thing, contact):
    response = client.get(
        "/contact",
        params={
            "sort": "things",
            "order": "asc",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert contact.id in [item["id"] for item in data["items"]]
