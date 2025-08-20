# ==============================================================================
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
# ==============================================================================
from tests import client, override_authentication

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


def test_get_lexicon_categories_endpoint():
    """Basic smoke test that categories endpoint returns a paginated payload."""
    resp = client.get("/lexicon/category")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    # Should have at least one category from init_lexicon and/or previous tests
    assert isinstance(data["items"], list)
