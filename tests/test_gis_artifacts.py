# ===============================================================================
# Copyright 2026 ross
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
"""Guards on the generated QGIS and ArcGIS Pro artifacts.

These assert the invariants a broken artifact would violate silently -- the
file still parses, still downloads, and only fails when a GIS user opens it
hours later. Loading a .qlr into a real QGIS is the check that actually proves
the format, and QGIS is not a CI dependency; see
docs/ogc-desktop-gis-artifacts.md for the manual procedure and what it covered.
"""

import json
import xml.etree.ElementTree as ET

import pytest

from core.ogc_field_metadata import table_entries
from tests import client
from core.pygeoapi import EDR_COLLECTIONS, THING_COLLECTIONS
from services.gis_artifacts import (
    Connection,
    arcgis_layer_file,
    field_value_maps,
    find_curated_layer,
    load_curated_layers,
    qgis_connections_xml,
    qgis_datasource_uri,
    qgis_layer_definition,
)

BASE = "https://example.org/ogcapi"


@pytest.fixture(scope="module")
def layers():
    return load_curated_layers()


def test_curated_config_parses(layers):
    assert layers, "gis-curated-layers.yml declares no layers."


@pytest.mark.parametrize("layer_id", [layer.id for layer in load_curated_layers()])
def test_qlr_is_well_formed_and_points_at_the_collection(layer_id):
    layer = find_curated_layer(layer_id)
    root = ET.fromstring(qgis_layer_definition(layer, BASE))

    assert root.tag == "qlr"
    maplayer = root.find("./maplayers/maplayer")
    assert maplayer.findtext("provider") == "OAPIF"
    assert maplayer.findtext("datasource") == qgis_datasource_uri(
        BASE, layer.collection
    )
    # The layer-tree entry and the maplayer must agree, or QGIS loads the tree
    # node and finds no layer behind it.
    tree_layer = root.find("./layer-tree-group/layer-tree-layer")
    assert tree_layer.get("source") == maplayer.findtext("datasource")
    assert tree_layer.get("id") == maplayer.findtext("id")


@pytest.mark.parametrize("layer_id", [layer.id for layer in load_curated_layers()])
def test_qlr_renderer_field_exists_on_the_collection(layer_id):
    """A renderer pointed at a field the view does not have renders nothing."""
    layer = find_curated_layer(layer_id)
    field = layer.renderer.get("field")
    if field is None:
        pytest.skip("single-symbol renderer classifies on no field")
    assert field in table_entries(layer.collection), (
        f"{layer.id} classifies on {field!r}, which has no entry for "
        f"{layer.collection} in core/ogc-field-descriptions.yml."
    )


@pytest.mark.parametrize("layer_id", [layer.id for layer in load_curated_layers()])
def test_qlr_aliases_cover_every_documented_field(layer_id):
    layer = find_curated_layer(layer_id)
    root = ET.fromstring(qgis_layer_definition(layer, BASE))
    aliased = {a.get("field") for a in root.findall(".//aliases/alias")}
    assert aliased == set(table_entries(layer.collection))


def test_qlr_value_map_entries_are_nested_option_maps():
    """QGIS 4.0.1 segfaults on a flattened value map rather than erroring.

    Each entry must be its own <Option type="Map"> wrapper whose single child
    is named for the display label and carries the stored value.
    """
    layer = next(
        layer
        for layer in load_curated_layers()
        if layer.renderer.get("type") == "categorized"
    )
    root = ET.fromstring(qgis_layer_definition(layer, BASE))
    entries = root.findall(
        ".//fieldConfiguration/field/editWidget/config/Option/Option/Option"
    )
    assert entries, "categorized layer emitted no value map"
    for entry in entries:
        assert entry.get("type") == "Map"
        children = list(entry)
        assert len(children) == 1
        assert children[0].get("type") == "QString"


def test_value_maps_skip_identity_mappings():
    """A label equal to its stored value is noise, not documentation."""
    for layer in load_curated_layers():
        for mapping in field_value_maps(layer).values():
            assert all(label != value for label, value in mapping.items())


def _served_feature_collections() -> set[str]:
    """Every OGC API - Features collection this branch actually publishes.

    Two sources, because the collection list is split: the thing collections
    are built in core/pygeoapi.py, and the derived/summary ones are declared
    in the core/pygeoapi-config.yml template.
    """
    import re
    from pathlib import Path

    served = {c["id"] for c in THING_COLLECTIONS}
    template = Path("core/pygeoapi-config.yml").read_text(encoding="utf-8")
    body = template.split("resources:", 1)[-1]
    served |= set(re.findall(r"^  ([a-z0-9_]+):", body, re.MULTILINE))
    return served


def test_every_curated_layer_names_a_collection_this_branch_serves():
    """A curated layer pointing at a collection we do not publish 404s in QGIS.

    Production advertises more collections than this branch defines, so a
    layer list written against a live deployment can name one that does not
    exist here.
    """
    served = _served_feature_collections()
    missing = {
        layer.id: layer.collection
        for layer in load_curated_layers()
        if layer.collection not in served
    }
    assert not missing, (
        f"{missing} name collections this branch does not serve. "
        f"Served: {sorted(served)}"
    )


def test_no_curated_layer_points_at_an_edr_collection():
    """Neither desktop client has an EDR reader; such a layer cannot open."""
    edr = {collection["id"] for collection in EDR_COLLECTIONS}
    offenders = [layer.id for layer in load_curated_layers() if layer.collection in edr]
    assert not offenders, (
        f"{offenders} point at EDR-only collections {sorted(edr)}, which "
        "publish no /items endpoint."
    )


def test_connections_xml_shape():
    xml = qgis_connections_xml(
        [Connection("A", "https://a.example/ogcapi"), Connection("B", "https://b/x")]
    )
    root = ET.fromstring(xml.split("\n", 1)[1])
    assert root.tag == "qgsWFSConnections"
    assert root.get("version") == "1.0"
    entries = root.findall("wfs")
    assert [e.get("name") for e in entries] == ["A", "B"]
    for entry in entries:
        # Without this QGIS registers a classic WFS connection instead, which
        # then fails against a service that speaks only OGC API - Features.
        assert entry.get("version") == "OGC_API_FEATURES"


def test_connections_xml_escapes_the_connection_name():
    xml = qgis_connections_xml([Connection('Ampersand & "quote"', BASE)])
    root = ET.fromstring(xml.split("\n", 1)[1])
    assert root.find("wfs").get("name") == 'Ampersand & "quote"'


def test_no_artifact_embeds_a_credential():
    """Per-user keys must never be baked into a shared file."""
    for layer in load_curated_layers():
        qlr = qgis_layer_definition(layer, BASE)
        lyrx = arcgis_layer_file(layer, BASE)
        for body in (qlr, lyrx):
            lowered = body.lower()
            assert "password" not in lowered
            assert "token" not in lowered
    connections = qgis_connections_xml([Connection("A", BASE)])
    assert "password" not in connections.lower()
    assert "username" not in connections.lower()


@pytest.mark.parametrize("layer_id", [layer.id for layer in load_curated_layers()])
def test_lyrx_is_valid_cim_json(layer_id):
    layer = find_curated_layer(layer_id)
    doc = json.loads(arcgis_layer_file(layer, BASE))

    assert doc["type"] == "CIMLayerDocument"
    definition = doc["layerDefinitions"][0]
    assert definition["type"] == "CIMFeatureLayer"
    # The layer's uRI must be listed in `layers`, or Pro shows an empty file.
    assert definition["uRI"] in doc["layers"]

    connection = definition["featureTable"]["dataConnection"]
    assert connection["type"] == "CIMOGCAPIServiceConnection"
    assert connection["serviceName"] == layer.collection
    assert connection["serverConnection"]["URL"] == BASE


@pytest.mark.parametrize("layer_id", [layer.id for layer in load_curated_layers()])
def test_lyrx_renderer_matches_the_qlr_renderer(layer_id):
    """The two clients must not disagree about how a layer is symbolised."""
    layer = find_curated_layer(layer_id)
    renderer = json.loads(arcgis_layer_file(layer, BASE))["layerDefinitions"][0][
        "renderer"
    ]
    expected = {
        "single": "CIMSimpleRenderer",
        "categorized": "CIMUniqueValueRenderer",
        "graduated": "CIMClassBreaksRenderer",
    }[layer.renderer["type"]]
    assert renderer["type"] == expected

    if layer.renderer["type"] == "categorized":
        values = [
            value["fieldValues"][0]
            for group in renderer["groups"]
            for klass in group["classes"]
            for value in klass["values"]
        ]
        assert values == [str(item["value"]) for item in layer.renderer["categories"]]
    elif layer.renderer["type"] == "graduated":
        bounds = [brk["upperBound"] for brk in renderer["breaks"]]
        assert bounds == [item["upper"] for item in layer.renderer["classes"]]


# ============= EOF =============================================


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


def test_index_lists_every_curated_layer():
    response = client.get("/gis")
    assert response.status_code == 200
    for layer in load_curated_layers():
        assert f"qgis/layers/{layer.id}.qlr" in response.text
        assert f"arcgis/layers/{layer.id}.lyrx" in response.text


def test_connections_download_is_an_attachment():
    response = client.get("/gis/qgis/connections.xml")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "OGC_API_FEATURES" in response.text


def test_layer_downloads_carry_their_extension():
    layer = load_curated_layers()[0]
    qlr = client.get(f"/gis/qgis/layers/{layer.id}.qlr")
    assert qlr.status_code == 200
    assert f'filename="{layer.id}.qlr"' in qlr.headers["content-disposition"]

    lyrx = client.get(f"/gis/arcgis/layers/{layer.id}.lyrx")
    assert lyrx.status_code == 200
    assert json.loads(lyrx.text)["type"] == "CIMLayerDocument"


def test_unknown_layer_is_a_404():
    assert client.get("/gis/qgis/layers/not-a-layer.qlr").status_code == 404
    assert client.get("/gis/arcgis/layers/not-a-layer.lyrx").status_code == 404


def test_served_artifacts_use_the_advertised_pygeoapi_url():
    """The artifact must not send a client to a host pygeoapi will contradict."""
    from core.pygeoapi import _server_url

    response = client.get("/gis/qgis/connections.xml")
    assert _server_url() in response.text


def test_field_filter_trims_aliases_to_the_views_real_columns():
    """_defaults is a shared pool, not a set of universal columns.

    Unfiltered, a nine-column collection ships aliases for every documented
    field in the file -- including geothermal ones. ArcGIS Pro takes
    fieldDescriptions at its word, so the filter has to bite.
    """
    layer = find_curated_layer("water-level-trend")
    real = {"id", "name", "trend_category", "slope_ft_per_year"}

    unfiltered = ET.fromstring(qgis_layer_definition(layer, BASE))
    filtered = ET.fromstring(qgis_layer_definition(layer, BASE, real))

    all_aliases = {a.get("field") for a in unfiltered.findall(".//aliases/alias")}
    kept = {a.get("field") for a in filtered.findall(".//aliases/alias")}

    assert kept == real
    assert len(all_aliases) > len(kept)
    # A field from another table's block must not survive the filter.
    assert "api" in all_aliases and "api" not in kept

    described = json.loads(arcgis_layer_file(layer, BASE, real))["layerDefinitions"][0][
        "featureTable"
    ]["fieldDescriptions"]
    assert {f["fieldName"] for f in described} == real


@pytest.mark.parametrize(
    "template,path,expected",
    [
        ("/gis/qgis/connections.xml", "/gis/qgis/connections.xml", "text/xml"),
        (
            "/gis/qgis/layers/{layer_id}.qlr",
            "/gis/qgis/layers/water-wells.qlr",
            "text/xml",
        ),
        (
            "/gis/arcgis/layers/{layer_id}.lyrx",
            "/gis/arcgis/layers/water-wells.lyrx",
            "application/json",
        ),
    ],
)
def test_openapi_advertises_the_content_type_actually_returned(
    template, path, expected
):
    """The schema and the response must not disagree.

    These routes return a raw Response with its own media type, so a
    `response_class` chosen for convenience rather than accuracy documents a
    content type the endpoint never sends. Both now come from the same
    Response subclass; this pins them together.
    """
    schema = client.get("/openapi.json").json()
    documented = set(schema["paths"][template]["get"]["responses"]["200"]["content"])
    assert documented == {expected}

    served = client.get(path).headers["content-type"]
    assert served.split(";")[0] == expected


def test_index_defaults_to_html_and_negotiates_json():
    assert client.get("/gis").headers["content-type"].startswith("text/html")
    assert (
        client.get("/gis", params={"f": "json"})
        .headers["content-type"]
        .startswith("application/json")
    )
    assert (
        client.get("/gis", headers={"Accept": "application/json"})
        .headers["content-type"]
        .startswith("application/json")
    )


def test_json_index_lets_a_frontend_enumerate_instead_of_hardcoding():
    payload = client.get("/gis", params={"f": "json"}).json()
    assert [entry["id"] for entry in payload["layers"]] == [
        layer.id for layer in load_curated_layers()
    ]
    for entry in payload["layers"]:
        assert {d["client"] for d in entry["downloads"]} == {"qgis", "arcgis"}


def test_json_index_hrefs_are_absolute_and_resolve():
    """A browser app on another origin has to be able to use them unchanged."""
    payload = client.get("/gis", params={"f": "json"}).json()
    hrefs = [payload["connections"][0]["href"]] + [
        download["href"]
        for entry in payload["layers"]
        for download in entry["downloads"]
    ]
    for href in hrefs:
        assert href.startswith("http://") or href.startswith("https://")
        response = client.get(href)
        assert response.status_code == 200, href


def test_json_index_media_types_match_what_the_download_sends():
    payload = client.get("/gis", params={"f": "json"}).json()
    for entry in payload["layers"]:
        for download in entry["downloads"]:
            served = client.get(download["href"])
            assert served.headers["content-type"].split(";")[0] == (
                download["media_type"]
            )
            assert download["filename"] in served.headers["content-disposition"]


def test_missing_layer_404_is_documented():
    schema = client.get("/openapi.json").json()
    for path in (
        "/gis/qgis/layers/{layer_id}.qlr",
        "/gis/arcgis/layers/{layer_id}.lyrx",
    ):
        assert "404" in schema["paths"][path]["get"]["responses"]
