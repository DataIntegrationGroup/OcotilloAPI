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
"""Shareable QGIS and ArcGIS Pro artifacts for the OGC API - Features mounts.

Two levels, per client:

* a **connection file** that registers the whole service in one import, so the
  user browses our collections in their Browser/Catalog panel;
* a handful of **layer files** carrying symbology, field aliases, value maps
  and scale visibility, for the user who only wants one curated view.

WHY THESE ARE GENERATED, NOT COMMITTED
--------------------------------------
Every artifact embeds an absolute service URL, and there are three of them
(production, staging, local) plus two mounts (`/ogcapi`, `/ogcapi-internal`).
Committing static files would mean six copies of each, each of which goes stale
the moment a collection is added -- and production already advertises 30
collections against the 13 defined in ``core/pygeoapi.py``. Generating from the
running app means the URL is always the one the caller reached us on.

WHAT IS DERIVED, AND FROM WHERE
-------------------------------
* Field aliases and value maps come from ``core/ogc-field-descriptions.yml``
  via ``core.ogc_field_metadata`` -- the same file that feeds ``/schema`` and
  ``/queryables``. A renamed field therefore cannot drift between the API and
  the shipped layer files.
* The curated layer list, symbology and scale thresholds come from
  ``core/gis-curated-layers.yml``.

EDR IS DELIBERATELY ABSENT
--------------------------
``waterlevels`` and ``water_chemistry`` are served by the EDR provider only
(see ``EDR_COLLECTIONS`` in ``core/pygeoapi.py``) -- they publish no ``/items``
endpoint. Neither QGIS nor ArcGIS Pro ships an OGC API - EDR client, so a layer
file pointing at either would fail to open. The curated layers use the feature
collections that carry the same measurements summarised per site.

CREDENTIALS ARE NEVER EMBEDDED
------------------------------
The internal mount is gated by per-user API keys (see
``docs/internal-ogc-desktop-gis.md``). QGIS's connection format has ``username``
and ``password`` attributes and Esri's ``CIMInternetServerConnection`` has a
``user`` field, so embedding a credential is *possible* in both -- and is not
done here. A shared file carrying one person's key would defeat per-user
issuance and revocation. Internal artifacts ship credential-free and the user
attaches their own key once, in their own client.

Read ``docs/ogc-desktop-gis-artifacts.md`` before changing any of the emitted
formats.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import yaml

from core.ogc_field_metadata import default_title, table_entries

# QGIS stores OGC API - Features connections in the same settings tree as
# classic WFS ones, discriminated by this version string. Confirmed against
# QGIS 4.0.1: the key is `qgis/connections-wfs/<name>/version`.
QGIS_OAPIF_VERSION = "OGC_API_FEATURES"

# QGIS provider key for OGC API - Features. Distinct from "WFS" -- the OAPIF
# provider is a separate plugin (libprovider_wfs.so registers both).
QGIS_PROVIDER = "OAPIF"

# Page size requested by the generated artifacts. Both clients page through
# `items`; a larger page means fewer round trips on collections in the
# thousands, which is all of the well layers.
DEFAULT_PAGE_SIZE = 1000

_CURATED_CACHE: dict | None = None


def _curated_path() -> Path:
    return Path(__file__).resolve().parent.parent / "core" / "gis-curated-layers.yml"


@dataclass(frozen=True)
class Connection:
    """One service endpoint to register in a client."""

    name: str
    url: str


@dataclass
class CuratedLayer:
    """One curated layer, as declared in core/gis-curated-layers.yml."""

    id: str
    collection: str
    title: str
    abstract: str = ""
    geometry: str = "Point"
    min_scale: float | None = None
    renderer: dict = dataclass_field(default_factory=dict)


def load_curated_layers(refresh: bool = False) -> list[CuratedLayer]:
    """Parse the curated-layer config, once per process."""
    global _CURATED_CACHE
    if _CURATED_CACHE is None or refresh:
        raw = yaml.safe_load(_curated_path().read_text(encoding="utf-8")) or {}
        entries = raw.get("layers") or []
        if not isinstance(entries, list):
            raise ValueError("gis-curated-layers.yml: `layers` must be a list.")
        layers = []
        for entry in entries:
            missing = {"id", "collection", "title"} - set(entry)
            if missing:
                raise ValueError(
                    f"gis-curated-layers.yml: layer entry missing {sorted(missing)}."
                )
            renderer = entry.get("renderer") or {}
            if renderer.get("type") not in {"single", "graduated", "categorized"}:
                raise ValueError(
                    f"gis-curated-layers.yml: {entry['id']} has unsupported renderer "
                    f"type {renderer.get('type')!r}."
                )
            layers.append(
                CuratedLayer(
                    id=entry["id"],
                    collection=entry["collection"],
                    title=entry["title"],
                    abstract=entry.get("abstract", "") or "",
                    geometry=entry.get("geometry", "Point"),
                    min_scale=entry.get("min_scale"),
                    renderer=renderer,
                )
            )
        ids = [layer.id for layer in layers]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(
                f"gis-curated-layers.yml: duplicate layer ids {sorted(duplicates)}."
            )
        _CURATED_CACHE = layers
    return list(_CURATED_CACHE)


def find_curated_layer(layer_id: str) -> CuratedLayer | None:
    for layer in load_curated_layers():
        if layer.id == layer_id:
            return layer
    return None


# --------------------------------------------------------------------------
# Field documentation shared by both clients
# --------------------------------------------------------------------------


def collection_fields(session, collection: str) -> set[str] | None:
    """Column names of the view backing ``collection``, or None if absent.

    ``core/ogc-field-descriptions.yml``'s ``_defaults`` block is a shared pool,
    not a set of universal columns -- it carries well fields and geothermal
    fields side by side, and ``describe_fields`` only ever applies the ones a
    given view actually reflects. Without the same intersection here, a nine
    column collection ships aliases for forty-two fields: harmless in QGIS,
    which silently drops the ones it cannot match, but ArcGIS Pro takes
    ``fieldDescriptions`` at its word.

    Returns None when the view is not present, which happens on a branch whose
    migrations have not created it yet. The caller then falls back to the full
    entry list rather than emitting a layer file with no aliases at all.
    """
    from sqlalchemy import text

    row = (
        session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :table"
            ),
            {"table": f"ogc_{collection}"},
        )
        .scalars()
        .all()
    )
    return set(row) or None


def field_aliases(collection: str, fields: set[str] | None = None) -> dict[str, str]:
    """Human-readable label per field, from the OGC field-description YAML.

    ``fields`` restricts the result to columns the view really has; see
    ``collection_fields``. Omitting it emits every documented entry.
    """
    return {
        name: entry.get("title") or default_title(name)
        for name, entry in table_entries(collection).items()
        if fields is None or name in fields
    }


def field_value_maps(layer: "CuratedLayer") -> dict[str, dict[str, str]]:
    """Display-label -> stored-value mapping per field, for a client value map.

    Only fields whose label genuinely differs from the stored value get an
    entry. The lexicon-backed columns (``thing_type``, ``release_status`` and
    friends) store terms that already read as prose, so mapping them to
    themselves would add a few kilobytes of ``name == value`` noise per layer
    and give the user a dropdown that renames nothing. The curated renderer
    categories are the real case: ``increasing`` means the water table is
    falling, which no reader should have to know.
    """
    renderer = layer.renderer
    if renderer.get("type") != "categorized":
        return {}
    mapping = {
        str(item["label"]): str(item["value"])
        for item in renderer.get("categories", [])
        if str(item["label"]) != str(item["value"])
    }
    return {renderer["field"]: mapping} if mapping else {}


# --------------------------------------------------------------------------
# QGIS
# --------------------------------------------------------------------------


def qgis_connections_xml(connections: list[Connection]) -> str:
    """A QGIS Data Source Manager connections file.

    Format taken from ``QgsManageConnectionsDialog::saveWfsConnections`` --
    root ``qgsWFSConnections`` version 1.0, one ``wfs`` child per connection.
    Only the attributes we actually want to pin are written; QGIS fills the
    rest from its own defaults on import.

    Imported through **Browser panel > right-click "WFS / OGC API - Features"
    > Load Connections**.
    """
    lines = [
        "<!DOCTYPE connections>",
        '<qgsWFSConnections version="1.0">',
    ]
    for connection in connections:
        lines.append(
            "  <wfs "
            f"name={quoteattr(connection.name)} "
            f"url={quoteattr(connection.url)} "
            f'version="{QGIS_OAPIF_VERSION}" '
            f'pagesize="{DEFAULT_PAGE_SIZE}" '
            'pagingenabled="true" '
            'ignoreAxisOrientation="false" '
            'invertAxisOrientation="false" '
            "/>"
        )
    lines.append("</qgsWFSConnections>")
    return "\n".join(lines) + "\n"


def qgis_datasource_uri(base_url: str, collection: str) -> str:
    """The OAPIF provider URI for one collection."""
    return f"url='{base_url}' typename='{collection}' pageSize='{DEFAULT_PAGE_SIZE}'"


def _qgis_marker_symbol(name: str, color: str, size: float, shape: str, outline: str):
    return (
        f'      <symbol type="marker" name="{name}">\n'
        '        <layer class="SimpleMarker">\n'
        '          <Option type="Map">\n'
        f'            <Option name="name" type="QString" value="{shape}"/>\n'
        f'            <Option name="color" type="QString" value="{color}"/>\n'
        f'            <Option name="size" type="QString" value="{size}"/>\n'
        f'            <Option name="outline_color" type="QString" value="{outline}"/>\n'
        '            <Option name="outline_width" type="QString" value="0.2"/>\n'
        "          </Option>\n"
        "        </layer>\n"
        "      </symbol>"
    )


def _qgis_renderer(renderer: dict) -> str:
    kind = renderer["type"]
    shape = renderer.get("shape", "circle")
    outline = renderer.get("outline_color", "35,35,35,255")
    base_size = renderer.get("size", 2.4)

    if kind == "single":
        symbol = _qgis_marker_symbol(
            "0", renderer.get("color", "31,119,180,255"), base_size, shape, outline
        )
        return (
            '    <renderer-v2 type="singleSymbol">\n'
            "      <symbols>\n" + symbol + "\n      </symbols>\n"
            "    </renderer-v2>"
        )

    if kind == "categorized":
        categories, symbols = [], []
        for index, item in enumerate(renderer["categories"]):
            categories.append(
                f'        <category value={quoteattr(str(item["value"]))} '
                f'symbol="{index}" label={quoteattr(item["label"])} render="true"/>'
            )
            symbols.append(
                _qgis_marker_symbol(
                    str(index),
                    item["color"],
                    item.get("size", base_size),
                    shape,
                    outline,
                )
            )
        return (
            f'    <renderer-v2 type="categorizedSymbol" '
            f'attr={quoteattr(renderer["field"])}>\n'
            "      <categories>\n" + "\n".join(categories) + "\n      </categories>\n"
            "      <symbols>\n" + "\n".join(symbols) + "\n      </symbols>\n"
            "    </renderer-v2>"
        )

    ranges, symbols = [], []
    for index, item in enumerate(renderer["classes"]):
        ranges.append(
            f'        <range lower="{item["lower"]}" upper="{item["upper"]}" '
            f'symbol="{index}" label={quoteattr(item["label"])} render="true"/>'
        )
        symbols.append(
            _qgis_marker_symbol(
                str(index), item["color"], item.get("size", base_size), shape, outline
            )
        )
    return (
        f'    <renderer-v2 type="graduatedSymbol" '
        f'attr={quoteattr(renderer["field"])} graduatedMethod="GraduatedColor">\n'
        "      <ranges>\n" + "\n".join(ranges) + "\n      </ranges>\n"
        "      <symbols>\n" + "\n".join(symbols) + "\n      </symbols>\n"
        "    </renderer-v2>"
    )


def qgis_layer_definition(
    layer: CuratedLayer, base_url: str, fields: set[str] | None = None
) -> str:
    """A QGIS layer definition (.qlr) for one curated layer.

    Deliberately minimal: QGIS fills every element this omits with its own
    defaults on load. Verified against QGIS 4.0.1 -- the emitted file loads to
    a valid layer with the renderer, aliases and scale visibility applied.
    """
    uri = qgis_datasource_uri(base_url, layer.collection)
    aliases = field_aliases(layer.collection, fields)
    value_maps = field_value_maps(layer)

    alias_lines = [
        f'        <alias field={quoteattr(name)} index="{index}" '
        f"name={quoteattr(title)}/>"
        for index, (name, title) in enumerate(sorted(aliases.items()))
    ]

    # A value map relabels the stored token in the attribute table and the
    # feature form. Shape copied from what QGIS itself writes: the "map" List
    # holds one nested <Option type="Map"> per entry, whose single child is
    # named for the DISPLAY label and carries the STORED value. Flattening
    # that wrapper away segfaults QGIS 4.0.1 on load rather than erroring.
    widget_lines = []
    for name, mapping in sorted(value_maps.items()):
        options = "".join(
            '              <Option type="Map">\n'
            f"                <Option name={quoteattr(label)} "
            f'type="QString" value={quoteattr(value)}/>\n'
            "              </Option>\n"
            for label, value in mapping.items()
        )
        widget_lines.append(
            f'        <field configurationFlags="NoFlag" name={quoteattr(name)}>\n'
            '          <editWidget type="ValueMap">\n'
            "            <config>\n"
            '              <Option type="Map">\n'
            '                <Option name="map" type="List">\n'
            f"{options}"
            "                </Option>\n"
            "              </Option>\n"
            "            </config>\n"
            "          </editWidget>\n"
            "        </field>"
        )

    scale_attrs = ""
    if layer.min_scale:
        scale_attrs = (
            f' hasScaleBasedVisibilityFlag="1" minScale="{layer.min_scale}"'
            ' maxScale="0"'
        )

    field_config = ""
    if widget_lines:
        field_config = (
            "      <fieldConfiguration>\n"
            + "\n".join(widget_lines)
            + "\n      </fieldConfiguration>\n"
        )

    return (
        "<!DOCTYPE qgis-layer-definition>\n"
        "<qlr>\n"
        '  <layer-tree-group name="">\n'
        f"    <layer-tree-layer id={quoteattr(layer.id)} "
        f"name={quoteattr(layer.title)} "
        f'providerKey="{QGIS_PROVIDER}" checked="Qt::Checked" expanded="1" '
        f"source={quoteattr(uri)}>\n"
        "      <customproperties/>\n"
        "    </layer-tree-layer>\n"
        "  </layer-tree-group>\n"
        "  <maplayers>\n"
        f'    <maplayer type="vector" geometry="{layer.geometry}"{scale_attrs}>\n'
        f"      <id>{escape(layer.id)}</id>\n"
        f"      <datasource>{escape(uri)}</datasource>\n"
        f"      <layername>{escape(layer.title)}</layername>\n"
        f"      <abstract>{escape(layer.abstract)}</abstract>\n"
        "      <srs><spatialrefsys><authid>OGC:CRS84</authid></spatialrefsys></srs>\n"
        f"      <provider>{QGIS_PROVIDER}</provider>\n"
        f"{_qgis_renderer(layer.renderer)}\n"
        "      <aliases>\n" + "\n".join(alias_lines) + "\n      </aliases>\n"
        f"{field_config}"
        "    </maplayer>\n"
        "  </maplayers>\n"
        "</qlr>\n"
    )


# --------------------------------------------------------------------------
# ArcGIS Pro
# --------------------------------------------------------------------------

# CIM types per Esri's published spec (Esri/cim-spec, docs/v3):
# CIMOGCAPIServiceConnection carries serviceName + serverConnection, and
# CIMInternetServerConnection carries the URL. The spec marks the connection's
# `password` "not persisted in documents", which is the same reason the
# internal artifacts here carry no credential.
CIM_VERSION = "3.3.0"


def _cim_color(rgba: str) -> dict:
    r, g, b, a = (int(part) for part in rgba.split(","))
    return {"type": "CIMRGBColor", "values": [r, g, b, round(a / 255 * 100, 2)]}


def _cim_marker(rgba: str, size: float) -> dict:
    return {
        "type": "CIMPointSymbol",
        "symbolLayers": [
            {
                "type": "CIMVectorMarker",
                "enable": True,
                "size": size * 2,
                "frame": {"xmin": -2, "ymin": -2, "xmax": 2, "ymax": 2},
                "markerGraphics": [
                    {
                        "type": "CIMMarkerGraphic",
                        "geometry": {"x": 0, "y": 0},
                        "symbol": {
                            "type": "CIMPolygonSymbol",
                            "symbolLayers": [
                                {
                                    "type": "CIMSolidFill",
                                    "enable": True,
                                    "color": _cim_color(rgba),
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _cim_renderer(renderer: dict) -> dict:
    kind = renderer["type"]
    size = renderer.get("size", 2.4)

    if kind == "single":
        return {
            "type": "CIMSimpleRenderer",
            "patch": "Default",
            "symbol": {
                "type": "CIMSymbolReference",
                "symbol": _cim_marker(renderer.get("color", "31,119,180,255"), size),
            },
        }

    if kind == "categorized":
        groups = [
            {
                "type": "CIMUniqueValueGroup",
                "classes": [
                    {
                        "type": "CIMUniqueValueClass",
                        "label": item["label"],
                        "patch": "Default",
                        "symbol": {
                            "type": "CIMSymbolReference",
                            "symbol": _cim_marker(
                                item["color"], item.get("size", size)
                            ),
                        },
                        "values": [
                            {
                                "type": "CIMUniqueValue",
                                "fieldValues": [str(item["value"])],
                            }
                        ],
                        "visible": True,
                    }
                    for item in renderer["categories"]
                ],
            }
        ]
        return {
            "type": "CIMUniqueValueRenderer",
            "fields": [renderer["field"]],
            "groups": groups,
            "useDefaultSymbol": True,
        }

    return {
        "type": "CIMClassBreaksRenderer",
        "classBreakType": "GraduatedColor",
        "classificationMethod": "Manual",
        "field": renderer["field"],
        "breaks": [
            {
                "type": "CIMClassBreak",
                "label": item["label"],
                "patch": "Default",
                "upperBound": item["upper"],
                "symbol": {
                    "type": "CIMSymbolReference",
                    "symbol": _cim_marker(item["color"], item.get("size", size)),
                },
            }
            for item in renderer["classes"]
        ],
    }


def arcgis_layer_file(
    layer: CuratedLayer, base_url: str, fields: set[str] | None = None
) -> str:
    """An ArcGIS Pro layer file (.lyrx) for one curated layer.

    NOTE: unlike the QGIS artifacts, this has NOT been verified by opening it
    in the target client -- no ArcGIS Pro is available to this project. It is
    built to Esri's published CIM spec. Treat the first open in Pro as the real
    test. See docs/ogc-desktop-gis-artifacts.md.
    """
    aliases = field_aliases(layer.collection, fields)
    connection = {
        "type": "CIMOGCAPIServiceConnection",
        "serviceName": layer.collection,
        "serverConnection": {
            "type": "CIMInternetServerConnection",
            "anonymous": True,
            "hideUserProperty": True,
            "URL": base_url,
        },
    }

    definition = {
        "type": "CIMLayerDocument",
        "version": CIM_VERSION,
        "layers": [f"CIMPATH=/{layer.id}.xml"],
        "layerDefinitions": [
            {
                "type": "CIMFeatureLayer",
                "name": layer.title,
                "uRI": f"CIMPATH=/{layer.id}.xml",
                "description": layer.abstract,
                "visibility": True,
                "expanded": True,
                "layerType": "Operational",
                "minScale": layer.min_scale or 0,
                "maxScale": 0,
                "featureTable": {
                    "type": "CIMFeatureTable",
                    "displayField": "name",
                    "editable": False,
                    "dataConnection": connection,
                    "studyAreaSpatialRel": "esriSpatialRelUndefined",
                    "searchOrder": "esriSearchOrderSpatial",
                    "fieldDescriptions": [
                        {
                            "type": "CIMFieldDescription",
                            "alias": title,
                            "fieldName": name,
                            "visible": True,
                            "searchMode": "Exact",
                        }
                        for name, title in sorted(aliases.items())
                    ],
                },
                "renderer": _cim_renderer(layer.renderer),
                "scaleSymbols": True,
                "snappable": False,
            }
        ],
    }
    return json.dumps(definition, indent=2) + "\n"


# ============= EOF =============================================
