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
from tests import client


def test_add_publication():
    response = client.post(
        "/publication/add",
        json={
            "title": "Test Publication",
            "authors": ["Author One", "Author Two"],
            "year": 2025,
            "doi": "10.1000/testdoi",
            "url": "http://example.com/test-publication",
            "publication_type": "Thesis",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Publication"
    assert data["year"] == 2025
    assert data["doi"] == "10.1000/testdoi"
    assert data["url"] == "http://example.com/test-publication"
    assert data["publication_type"] == "Thesis"
    # Ensure that the authors are correctly formatted
    assert isinstance(data["authors"], list)
    assert len(data["authors"]) == 2
    assert data["authors"][0]["name"] == "Author One"
    assert data["authors"][1]["name"] == "Author Two"


# ============= EOF =============================================
