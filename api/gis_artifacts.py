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
"""Downloadable QGIS and ArcGIS Pro artifacts for the OGC API mounts.

The public routes are deliberately anonymous: they describe the public
`/ogcapi` mount, which is itself anonymous, and a desktop GIS user fetching a
connection file has no credential to present. Nothing they return is
sensitive -- the URLs are already advertised in the pygeoapi landing page, and
no credential is ever embedded (see services/gis_artifacts).

The internal connection file is gated, not because the file is secret, but
because the internal mount's existence is not something to advertise to
anonymous callers. Holding it still gets you nothing without an `OGCInternal`
API key.

Read docs/ogc-desktop-gis-artifacts.md before changing what is emitted.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from core.app import in_public_schema
from core.dependencies import session_dependency, viewer_dependency
from core.pygeoapi import _internal_server_url, _server_url
from services.gis_artifacts import (
    Connection,
    arcgis_layer_file,
    collection_fields,
    find_curated_layer,
    load_curated_layers,
    qgis_connections_xml,
    qgis_layer_definition,
)

router = APIRouter(prefix="/gis", tags=["desktop gis"])

PUBLIC_CONNECTION_NAME = "NMBGMR Ocotillo"
INTERNAL_CONNECTION_NAME = "NMBGMR Ocotillo (internal)"


def _attachment(body: str, media_type: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _public_base() -> str:
    # _server_url() is what pygeoapi stamps into its own `self`/`next` links.
    # Deriving the artifact's URL from the same place means a client that
    # imports the connection and then pages through `items` never crosses
    # hosts -- the failure mode that PYGEOAPI_INTERNAL_SERVER_URL was added to
    # fix (see the comment in core/pygeoapi._internal_server_url).
    return _server_url()


@router.get("/qgis/connections.xml", response_class=PlainTextResponse)
@in_public_schema
def qgis_connections() -> Response:
    """QGIS connections file registering the public OGC API - Features mount.

    Import through **Browser panel > right-click "WFS / OGC API - Features" >
    Load Connections**.
    """
    body = qgis_connections_xml([Connection(PUBLIC_CONNECTION_NAME, _public_base())])
    return _attachment(body, "text/xml", "ocotillo-ogcapi-connections.xml")


@router.get("/qgis/connections-internal.xml", response_class=PlainTextResponse)
def qgis_connections_internal(user: viewer_dependency) -> Response:
    """QGIS connections file covering the public and internal mounts.

    Carries no credential. The internal entry only resolves for a client that
    attaches its own `OGCInternal` API key -- see
    docs/internal-ogc-desktop-gis.md for how one is issued and attached.
    """
    body = qgis_connections_xml(
        [
            Connection(PUBLIC_CONNECTION_NAME, _public_base()),
            Connection(INTERNAL_CONNECTION_NAME, _internal_server_url()),
        ]
    )
    return _attachment(body, "text/xml", "ocotillo-ogcapi-connections-internal.xml")


@router.get("/qgis/layers/{layer_id}.qlr", response_class=PlainTextResponse)
@in_public_schema
def qgis_layer(layer_id: str, session: session_dependency) -> Response:
    """A styled QGIS layer definition for one curated layer."""
    layer = find_curated_layer(layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail=f"No curated layer {layer_id!r}.")
    fields = collection_fields(session, layer.collection)
    body = qgis_layer_definition(layer, _public_base(), fields)
    return _attachment(body, "text/xml", f"{layer_id}.qlr")


@router.get("/arcgis/layers/{layer_id}.lyrx", response_class=PlainTextResponse)
@in_public_schema
def arcgis_layer(layer_id: str, session: session_dependency) -> Response:
    """A styled ArcGIS Pro layer file for one curated layer."""
    layer = find_curated_layer(layer_id)
    if layer is None:
        raise HTTPException(status_code=404, detail=f"No curated layer {layer_id!r}.")
    fields = collection_fields(session, layer.collection)
    body = arcgis_layer_file(layer, _public_base(), fields)
    return _attachment(body, "application/json", f"{layer_id}.lyrx")


_PAGE_STYLE = (
    "max-width:52rem;margin:3rem auto;padding:0 1.25rem;"
    "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;"
    "line-height:1.6;color:#1a1a1a"
)


@router.get("", response_class=HTMLResponse)
@in_public_schema
def gis_index() -> HTMLResponse:
    """Landing page listing every downloadable artifact."""
    base = _public_base()
    rows = "".join(
        f"<tr><td><strong>{layer.title}</strong><br>"
        f"<span style='color:#555;font-size:.9em'>{layer.abstract}</span></td>"
        f'<td><a href="qgis/layers/{layer.id}.qlr">.qlr</a></td>'
        f'<td><a href="arcgis/layers/{layer.id}.lyrx">.lyrx</a></td></tr>'
        for layer in load_curated_layers()
    )
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>Desktop GIS downloads</title></head>
<body style="{_PAGE_STYLE}">
<h1>Using our OGC layers in QGIS and ArcGIS Pro</h1>
<p>Service URL: <code>{base}</code></p>

<h2>Everything at once</h2>
<p><a href="qgis/connections.xml"><strong>QGIS connections file</strong></a> &mdash;
in QGIS, open the <em>Browser</em> panel, right-click
<em>WFS / OGC API - Features</em>, choose <em>Load Connections</em>, and pick
this file. Every collection then appears in the Browser panel.</p>
<p><strong>ArcGIS Pro</strong> &mdash; Pro writes its own <code>.ogc</code>
connection file and we cannot generate one for you. Add the connection once:
<em>Insert &gt; Connections &gt; Server &gt; New OGC API Server</em>, and paste
the service URL above. Pro saves a <code>.ogc</code> file into your project
folder that you can then share with colleagues.</p>

<h2>One layer at a time</h2>
<p>Styled, with field aliases already applied. Drag the file into QGIS, or add
the <code>.lyrx</code> to a map in Pro.</p>
<table cellpadding="6" style="border-collapse:collapse">
<tr><th align="left">Layer</th><th>QGIS</th><th>ArcGIS Pro</th></tr>
{rows}
</table>

<h2>Time series</h2>
<p>Water levels and water chemistry are also published as
OGC API - EDR time series at <code>{base}/collections/waterlevels</code> and
<code>{base}/collections/water_chemistry</code>. Neither QGIS nor ArcGIS Pro
can read EDR, so the layers above carry the same measurements summarised per
site instead.</p>
</body></html>"""
    )


# ============= EOF =============================================
