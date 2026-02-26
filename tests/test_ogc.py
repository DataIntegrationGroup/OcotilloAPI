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
import pytest
from importlib.util import find_spec

from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)
from main import app
from tests import client, override_authentication

pytestmark = pytest.mark.skipif(
    find_spec("pygeoapi") is None,
    reason="pygeoapi is not installed in this environment",
)


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


def test_ogc_landing():
    response = client.get("/ogcapi")
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"]
    assert any(link["rel"] == "self" for link in payload["links"])


def test_ogc_conformance():
    response = client.get("/ogcapi/conformance")
    assert response.status_code == 200
    payload = response.json()
    assert "conformsTo" in payload
    assert any("ogcapi-features" in item for item in payload["conformsTo"])


def test_ogc_collections():
    response = client.get("/ogcapi/collections")
    assert response.status_code == 200
    payload = response.json()
    ids = {collection["id"] for collection in payload["collections"]}
    assert {"locations", "water_wells", "springs"}.issubset(ids)


@pytest.mark.skip("PostGIS spatial operators not available in CI - see issue #449")
def test_ogc_locations_items_bbox(location):
    bbox = "-107.95,33.80,-107.94,33.81"
    response = client.get(f"/ogcapi/collections/locations/items?bbox={bbox}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["numberReturned"] >= 1


def test_ogc_wells_items_and_item(water_well_thing):
    response = client.get("/ogcapi/collections/water_wells/items?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
    ids = {feature["id"] for feature in payload["features"]}
    assert str(water_well_thing.id) in ids

    response = client.get(
        f"/ogcapi/collections/water_wells/items/{water_well_thing.id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["id"], str)
    assert payload["id"] == str(water_well_thing.id)


@pytest.mark.skip("PostGIS spatial operators not available in CI - see issue #449")
def test_ogc_polygon_within_filter(location):
    polygon = "POLYGON((-107.95 33.80,-107.94 33.80,-107.94 33.81,-107.95 33.81,-107.95 33.80))"
    response = client.get(
        "/ogcapi/collections/locations/items",
        params={
            "filter": f"WITHIN(geometry,{polygon})",
            "filter-lang": "cql2-text",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
