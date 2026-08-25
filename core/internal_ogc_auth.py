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
"""ASGI auth gate for the authenticated internal OGC mount (/ogcapi-internal).

pygeoapi is mounted via a raw Starlette Mount (core/pygeoapi.py), so FastAPI's
Depends() machinery never runs for it -- gating has to happen at the ASGI
layer, in front of the mount. This is a plain ASGI middleware class rather
than @app.middleware("http")/BaseHTTPMiddleware (used elsewhere in this
codebase): BaseHTTPMiddleware buffers the full response body and interferes
with client-disconnect propagation, which matters here since
/ogcapi-internal serves paginated GeoJSON up to `max_items: 10000`. On the
success path this calls straight through with zero buffering.

Kept separate from core/permissions.py to avoid a circular import with
core/pygeoapi.py.

Three credential transports are accepted, because the desktop GIS clients
this mount exists for cannot all carry an Authentik bearer token:

  * ``Authorization: Bearer <jwt>`` -- QGIS's OAuth2 authentication method,
    scripts, and anything that can talk to Authentik directly.
  * ``Authorization: Basic <base64(user:secret)>`` -- the only scheme ArcGIS
    Pro's "Add OGC API connection" dialog supports with saved credentials
    (Authentication > Server Authentication). Esri does not support
    token-secured OGC service connections at all.
  * ``?token=<secret>`` -- ArcGIS Pro's "Custom request parameters", which the
    client re-appends to every request it issues. Also a workaround for the
    QGIS regression where OGC API - Features requests dropped the
    Authorization header (qgis/QGIS#60473).

The Basic and query-parameter transports carry a *static API key* (see
`api_key_label`) rather than a JWT, since neither ArcGIS nor QGIS can refresh
an Authentik access token before it expires. A bearer JWT is still accepted
and still checked for INTERNAL_OGC_GROUP membership; an API key is a
pre-authorized stand-in for that same group.

The query-parameter transport puts the secret in the request URL, which App
Engine's request log records. Prefer Basic where the client supports it, and
treat keys handed out for ArcGIS as log-exposed when rotating.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Receive, Scope, Send

from core import permissions
from core.settings import settings

# Comma- or whitespace-separated `label:sha256hex` entries. The label is for
# operator bookkeeping (who holds this key) and never appears in a response.
API_KEYS_ENV = "INTERNAL_OGC_API_KEYS"

# Query parameter carrying a credential. Stripped before the request reaches
# pygeoapi so it cannot trip pygeoapi's unknown-parameter handling or leak
# into a provider's filter parsing.
TOKEN_QUERY_PARAM = "token"

# Sent on 401 so ArcGIS Pro and QGIS surface a credential prompt instead of a
# bare failure.
WWW_AUTHENTICATE = 'Basic realm="Ocotillo Internal OGC API", charset="UTF-8"'


def _configured_api_keys() -> dict[str, str]:
    """Parse API_KEYS_ENV into {label: sha256hex}.

    Read fresh on every call for the same reason
    permissions.authentication_disabled() is: an import-time snapshot diverges
    from a value changed after import, and the two checks disagreeing is how
    the earlier auth bugs in this codebase presented.

    Malformed entries are skipped rather than raising. A typo in one entry
    must not take the whole mount down for every other key holder.
    """
    raw = os.environ.get(API_KEYS_ENV) or ""
    keys: dict[str, str] = {}
    for entry in raw.replace(",", " ").split():
        label, sep, digest = entry.partition(":")
        digest = digest.strip().lower()
        if not sep or not label.strip() or len(digest) != 64:
            continue
        try:
            int(digest, 16)
        except ValueError:
            continue
        keys[label.strip()] = digest
    return keys


def api_key_label(secret: str) -> str | None:
    """Return the configured label for `secret`, or None if it matches none.

    Compared as SHA-256 hex with hmac.compare_digest so neither the stored
    material nor the comparison timing reveals a valid key.
    """
    configured = _configured_api_keys()
    if not configured:
        return None
    presented = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    for label, expected in configured.items():
        if hmac.compare_digest(presented, expected):
            return label
    return None


def _extract_credential(scope: Scope) -> str | None:
    """Pull a credential out of the Authorization header or ?token=.

    Header wins over query parameter, and within the header both Bearer and
    Basic are accepted. For Basic, the password half carries the secret
    (username ignored, conventionally "apikey"); a Basic credential with an
    empty password falls back to the username so pasting a key into either
    field of a connection dialog works.
    """
    headers = dict(scope.get("headers") or [])
    authorization = headers.get(b"authorization")
    if authorization:
        scheme, _, param = authorization.decode("latin-1").partition(" ")
        scheme = scheme.lower()
        param = param.strip()
        if scheme == "bearer" and param:
            return param
        if scheme == "basic" and param:
            try:
                decoded = base64.b64decode(param, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                return None
            username, sep, password = decoded.partition(":")
            if not sep:
                return None
            return password or username or None
        return None

    for key, value in parse_qsl(
        (scope.get("query_string") or b"").decode("latin-1"), keep_blank_values=True
    ):
        if key == TOKEN_QUERY_PARAM and value:
            return value
    return None


def _strip_token_query_param(scope: Scope) -> Scope:
    """Return `scope` with any ?token= removed, copied only if it was present.

    pygeoapi echoes the incoming query string into the `self` and `next` links
    it emits; leaving the secret in place would publish it in every response
    body as well as in the request log.
    """
    query_string = scope.get("query_string") or b""
    if TOKEN_QUERY_PARAM.encode("latin-1") not in query_string:
        return scope
    pairs = parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)
    remaining = [(k, v) for k, v in pairs if k != TOKEN_QUERY_PARAM]
    if len(remaining) == len(pairs):
        return scope
    scope = dict(scope)
    scope["query_string"] = urlencode(remaining).encode("latin-1")
    return scope


async def _send_json(
    send: Send, status_code: int, detail: str, *, challenge: bool = False
) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if challenge:
        headers.append((b"www-authenticate", WWW_AUTHENTICATE.encode("latin-1")))
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


class InternalOGCAuthMiddleware:
    """Gates every request under `mount_path` behind an API key or
    INTERNAL_OGC_GROUP membership; requests to any other path pass straight
    through untouched.

    Registered via app.add_middleware(), which wraps the whole app -- the
    path check below is what keeps this scoped to the internal mount only.
    """

    def __init__(self, app: ASGIApp, mount_path: str) -> None:
        self.app = app
        self.mount_path = mount_path

    def _covers(self, path: str) -> bool:
        # Segment-boundary match, not a bare startswith: with mount_path
        # "/ogcapi" a plain prefix test would also swallow "/ogcapi-internal".
        return path == self.mount_path or path.startswith(f"{self.mount_path}/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._covers(scope["path"]):
            await self.app(scope, receive, send)
            return

        if permissions.authentication_disabled():
            if settings.mode != permissions.BYPASS_ALLOWED_MODE:
                # HTTPException(424) (what core.permissions.authenticated()
                # raises for this same misconfiguration) means nothing from
                # raw ASGI code -- send the response directly so a
                # misconfigured box degrades to "internal mount always 424s"
                # rather than crashing the worker.
                await _send_json(
                    send, 424, permissions.bypass_misconfiguration_detail()
                )
                return
            await self.app(_strip_token_query_param(scope), receive, send)
            return

        secret = _extract_credential(scope)
        if not secret:
            await _send_json(send, 401, "Unauthorized", challenge=True)
            return

        if api_key_label(secret) is None:
            # Not a static key, so it has to be an Authentik access token.
            try:
                payload = permissions.decode_token_payload(secret)
            except permissions.TokenInvalid:
                await _send_json(
                    send, 401, "Could not validate credentials", challenge=True
                )
                return

            if permissions.INTERNAL_OGC_GROUP not in payload.get("groups", []):
                await _send_json(send, 403, "Forbidden")
                return

        await self.app(_strip_token_query_param(scope), receive, send)


# ============= EOF =============================================
