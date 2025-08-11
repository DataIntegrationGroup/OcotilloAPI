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
from tests import client


def test_get_lexicon_terms_sort_categories_branch():
    """
    Ensure the special-case branch (sort == 'categories') in GET /lexicon is exercised.
    It should not apply sorting/filtering and still return a valid pagination payload.
    """
    resp = client.get("/lexicon", params={"sort": "categories"})
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
