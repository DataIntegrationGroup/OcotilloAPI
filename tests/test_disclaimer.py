# ===============================================================================
# Copyright 2026
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
from core.disclaimer import (
    DISCLAIMER_CONTACT_EMAIL,
    DISCLAIMER_PARAGRAPHS,
    DISCLAIMER_TITLE,
)
from tests import client


def test_disclaimer_html():
    response = client.get("/disclaimer")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

    body = response.text
    assert f"<h1>{DISCLAIMER_TITLE}</h1>" in body
    assert f'href="mailto:{DISCLAIMER_CONTACT_EMAIL}"' in body
    assert "New Mexico Bureau of Geology and Mineral Resources" in body
    assert body.count("<p>") == len(DISCLAIMER_PARAGRAPHS)


def test_disclaimer_json():
    response = client.get("/disclaimer", params={"f": "json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    payload = response.json()
    assert payload["title"] == DISCLAIMER_TITLE
    assert payload["contact"] == DISCLAIMER_CONTACT_EMAIL
    assert payload["paragraphs"] == list(DISCLAIMER_PARAGRAPHS)


def test_disclaimer_json_via_accept_header():
    response = client.get("/disclaimer", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_disclaimer_html_wins_when_browser_accepts_both():
    # Browsers send Accept: text/html,...,*/*, which must not be read as a
    # request for the JSON representation.
    response = client.get(
        "/disclaimer",
        headers={"Accept": "text/html,application/xhtml+xml,application/json;q=0.9"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_disclaimer_requires_no_authentication():
    # The pygeoapi configs advertise this URL as terms_of_service, so an OGC
    # client following the link has no credentials to present.
    response = client.get("/disclaimer")
    assert response.status_code == 200
