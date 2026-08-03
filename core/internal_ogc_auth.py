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
"""

import json
import os

from starlette.types import ASGIApp, Receive, Scope, Send

from core import permissions
from core.settings import settings


def _extract_bearer_token(scope: Scope) -> str | None:
    headers = dict(scope.get("headers") or [])
    authorization = headers.get(b"authorization")
    if not authorization:
        return None
    scheme, _, param = authorization.decode("latin-1").partition(" ")
    if scheme.lower() != "bearer" or not param:
        return None
    return param


async def _send_json(send: Send, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class InternalOGCAuthMiddleware:
    """Gates every request under `mount_path` behind INTERNAL_OGC_GROUP
    membership; requests to any other path pass straight through untouched.

    Registered via app.add_middleware(), which wraps the whole app -- the
    path check below is what keeps this scoped to the internal mount only.
    """

    def __init__(self, app: ASGIApp, mount_path: str) -> None:
        self.app = app
        self.mount_path = mount_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.mount_path):
            await self.app(scope, receive, send)
            return

        if int(os.environ.get("AUTHENTIK_DISABLE_AUTHENTICATION", 0)):
            if settings.mode == "production":
                # HTTPException(424) (what core.permissions.authenticated()
                # raises for this same misconfiguration) means nothing from
                # raw ASGI code -- send the response directly so a
                # misconfigured production box degrades to "internal mount
                # always 424s" rather than crashing the worker.
                await _send_json(
                    send,
                    424,
                    "Authentication is disabled in production mode. Set "
                    "AUTHENTIK_DISABLE_AUTHENTICATION=0 to enable authentication.",
                )
                return
            await self.app(scope, receive, send)
            return

        token = _extract_bearer_token(scope)
        if not token:
            await _send_json(send, 401, "Unauthorized")
            return

        try:
            payload = permissions.decode_token_payload(token)
        except permissions.TokenInvalid:
            await _send_json(send, 401, "Could not validate credentials")
            return

        if permissions.INTERNAL_OGC_GROUP not in payload.get("groups", []):
            await _send_json(send, 403, "Forbidden")
            return

        await self.app(scope, receive, send)


# ============= EOF =============================================
