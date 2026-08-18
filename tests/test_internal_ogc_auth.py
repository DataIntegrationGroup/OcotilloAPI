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
"""Credential handling for the internal OGC mount's ASGI auth gate.

The middleware runs outside FastAPI's Depends() machinery, so
`override_authentication()` and app.dependency_overrides do not reach it.
These tests drive a minimal Starlette app wrapped in the real middleware
instead of the full application, which keeps them independent of the database
and of whether pygeoapi's backing views exist.
"""

import base64
import hashlib
import secrets

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core import permissions
from core.internal_ogc_auth import (
    API_KEYS_ENV,
    InternalOGCAuthMiddleware,
    api_key_label,
)

MOUNT = "/ogcapi-internal"


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


async def _echo(request):
    # Echoes the query string the downstream app actually received, so the
    # ?token= stripping can be asserted from the client side.
    return JSONResponse({"query": request.url.query})


@pytest.fixture
def gate(monkeypatch):
    """Middleware under test with the dev bypass forced off.

    The bypass is enabled in CI for the suite as a whole; leaving it on would
    let every request through and assert nothing.
    """
    monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", "0")
    app = Starlette(
        routes=[
            Route(MOUNT, _echo),
            Route(f"{MOUNT}/collections", _echo),
            Route("/ogcapi/collections", _echo),
        ]
    )
    app.add_middleware(InternalOGCAuthMiddleware, mount_path=MOUNT)
    return TestClient(app)


@pytest.fixture
def api_key(monkeypatch):
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv(API_KEYS_ENV, f"arcgis-desktop:{_digest(key)}")
    return key


def test_public_mount_is_untouched(gate):
    # The gate wraps the whole app; only the internal mount may be affected.
    assert gate.get("/ogcapi/collections").status_code == 200


def test_missing_credential_is_challenged(gate):
    response = gate.get(f"{MOUNT}/collections")

    assert response.status_code == 401
    # Without this header neither ArcGIS Pro nor QGIS prompts for credentials.
    assert response.headers["www-authenticate"].startswith("Basic realm=")


def test_basic_auth_with_api_key_is_accepted(gate, api_key):
    credentials = base64.b64encode(f"apikey:{api_key}".encode()).decode()

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": f"Basic {credentials}"}
    )

    assert response.status_code == 200


def test_basic_auth_accepts_the_key_in_the_username_field(gate, api_key):
    # Connection dialogs that leave the password blank must still work.
    credentials = base64.b64encode(f"{api_key}:".encode()).decode()

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": f"Basic {credentials}"}
    )

    assert response.status_code == 200


def test_basic_auth_with_a_wrong_key_is_rejected(gate, api_key):
    credentials = base64.b64encode(b"apikey:not-the-key").decode()

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": f"Basic {credentials}"}
    )

    assert response.status_code == 401


def test_query_parameter_token_is_accepted_and_stripped(gate, api_key):
    response = gate.get(f"{MOUNT}/collections?limit=5&token={api_key}")

    assert response.status_code == 200
    # pygeoapi echoes the incoming query string into its self/next links, so
    # a token left in place would be published in every response body.
    assert "token" not in response.json()["query"]
    assert "limit=5" in response.json()["query"]


def test_query_parameter_token_is_rejected_when_wrong(gate, api_key):
    assert gate.get(f"{MOUNT}/collections?token=nope").status_code == 401


def test_bearer_api_key_is_accepted(gate, api_key):
    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": f"Bearer {api_key}"}
    )

    assert response.status_code == 200


def test_bearer_jwt_still_requires_the_internal_group(gate, monkeypatch):
    monkeypatch.setattr(
        permissions, "decode_token_payload", lambda token: {"groups": ["Viewer"]}
    )

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": "Bearer a-jwt"}
    )

    assert response.status_code == 403


def test_bearer_jwt_with_the_internal_group_is_accepted(gate, monkeypatch):
    monkeypatch.setattr(
        permissions,
        "decode_token_payload",
        lambda token: {"groups": [permissions.INTERNAL_OGC_GROUP]},
    )

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": "Bearer a-jwt"}
    )

    assert response.status_code == 200


def test_invalid_jwt_is_rejected(gate, monkeypatch):
    def _raise(token):
        raise permissions.TokenInvalid("bad signature")

    monkeypatch.setattr(permissions, "decode_token_payload", _raise)

    response = gate.get(
        f"{MOUNT}/collections", headers={"Authorization": "Bearer a-jwt"}
    )

    assert response.status_code == 401


def test_bypass_outside_development_fails_closed(gate, monkeypatch):
    monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", "1")
    monkeypatch.setenv("MODE", "production")

    response = gate.get(f"{MOUNT}/collections")

    assert response.status_code == 424


def test_no_configured_keys_means_no_key_is_valid(gate, monkeypatch):
    monkeypatch.delenv(API_KEYS_ENV, raising=False)

    assert api_key_label("anything") is None


def test_malformed_key_entries_do_not_disable_the_valid_ones(monkeypatch):
    good = secrets.token_urlsafe(32)
    monkeypatch.setenv(
        API_KEYS_ENV,
        f"missing-colon, short:abc123, blank-digest:, good:{_digest(good)}",
    )

    assert api_key_label(good) == "good"
    assert api_key_label("short") is None
