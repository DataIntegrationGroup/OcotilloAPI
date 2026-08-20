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
"""Authorization wiring tests.

CI runs with AUTHENTIK_DISABLE_AUTHENTICATION=1, so no test here can exercise
a real Authentik token. These tests cover the parts that are verifiable
without one:

* which routes have no authentication dependency at all (an inventory test --
  authorization is opt-in per endpoint, so a forgotten `user:` parameter
  silently publishes an endpoint and nothing else would catch it),
* that the anonymous OpenAPI schema advertises exactly those routes,
* the pure group-membership logic behind the role tiers,
* the startup guard on the development bypass.
"""

import pytest
from fastapi.routing import iter_route_contexts

from core import dependencies, permissions
from tests import client

# Routes that are allowed to have no authentication dependency. Adding an entry
# here is a deliberate decision to publish an endpoint anonymously -- it is not
# a formality to satisfy the test.
#
#   /health, /_ah/warmup      uptime monitors and App Engine warmup
#   /docs-auth, /openapi-auth Swagger UI and schema, no data
#   /disclaimer               advertised as terms_of_service by both pygeoapi
#                             mounts, so OGC clients fetch it uncredentialed
#   /ngwmn/*                  polled by the federal NGWMN harvester
#
# Not listed, because they never reach this scan:
#   /openapi.json, /docs, /redoc are bare Starlette routes with no dependant.
#   /ogcapi is a Mount -- anonymous by design; /ogcapi-internal is gated by
#   core.internal_ogc_auth.InternalOGCAuthMiddleware, outside Depends().
EXPECTED_ANONYMOUS_ROUTES = {
    ("GET", "/health"),
    ("GET", "/_ah/warmup"),
    ("GET", "/docs-auth"),
    ("GET", "/docs-auth/oauth2-redirect"),
    ("GET", "/openapi-auth.json"),
    ("GET", "/disclaimer"),
    ("GET", "/ngwmn/waterlevels/{pointid}"),
    ("GET", "/ngwmn/wellconstruction/{pointid}"),
    ("GET", "/ngwmn/lithology/{pointid}"),
}

# Every dependency callable built by core.permissions.authenticated().
AUTH_DEPENDENCY_CALLABLES = frozenset(
    {
        dependencies.admin_function,
        dependencies.editor_function,
        dependencies.viewer_function,
        dependencies.amp_admin_function,
        dependencies.amp_editor_function,
        dependencies.amp_viewer_function,
        dependencies.amp_staging_function,
        dependencies.lexicon_admin_function,
        dependencies.lexicon_editor_function,
        dependencies.no_permission_function,
    }
)


def _has_auth_dependency(dependant) -> bool:
    """Walk a route's dependency tree looking for an auth dependency."""
    if dependant.call in AUTH_DEPENDENCY_CALLABLES:
        return True
    return any(_has_auth_dependency(sub) for sub in dependant.dependencies)


def _anonymous_routes() -> set:
    """Every (method, path) with no authentication dependency.

    Walks iter_route_contexts() rather than app.routes: routes registered via
    include_router() are not flattened into app.routes in this FastAPI version,
    so a plain scan would see only the endpoints declared directly on `app` and
    this test would pass while reporting on ~5 of ~130 routes.
    """
    found = set()
    for route_context in iter_route_contexts(client.app.routes):
        dependant = getattr(route_context, "dependant", None)
        if dependant is None:
            # Not an APIRoute (Mounts, bare Starlette routes such as /docs).
            continue
        if _has_auth_dependency(dependant):
            continue
        path = route_context.path_format or route_context.path
        for method in route_context.methods or ():
            if method in ("HEAD", "OPTIONS"):
                continue
            found.add((method, path))
    return found


def test_no_unintended_anonymous_routes():
    """Every route without an auth dependency is one we chose to publish.

    Authorization is declared per endpoint as a `user: <role>_dependency`
    parameter, not at the router level, so omitting it produces a fully public
    endpoint with no error anywhere. This test is the only thing that notices.
    """
    unexpected = _anonymous_routes() - EXPECTED_ANONYMOUS_ROUTES
    assert not unexpected, (
        "These routes have no authentication dependency. Add a `user: "
        "<role>_dependency` parameter, or add them to "
        f"EXPECTED_ANONYMOUS_ROUTES if they are meant to be public: "
        f"{sorted(unexpected)}"
    )


def test_expected_anonymous_routes_still_exist():
    """Keeps EXPECTED_ANONYMOUS_ROUTES from rotting into a stale allowlist."""
    stale = EXPECTED_ANONYMOUS_ROUTES - _anonymous_routes()
    assert not stale, (
        "EXPECTED_ANONYMOUS_ROUTES lists routes that no longer exist or now "
        f"require authentication -- remove them: {sorted(stale)}"
    )


def test_public_schema_advertises_only_anonymous_routes():
    """@in_public_schema must not advertise an authenticated operation.

    Two /thing routes used to carry the decorator (then named @public_route)
    alongside a viewer_dependency, so the anonymous schema described endpoints
    that 401 for anonymous callers.
    """
    schema = client.get("/openapi.json").json()
    advertised = {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
    }
    assert advertised <= EXPECTED_ANONYMOUS_ROUTES, (
        "The anonymous OpenAPI schema advertises routes that require "
        "authentication. Remove @in_public_schema from them: "
        f"{sorted(advertised - EXPECTED_ANONYMOUS_ROUTES)}"
    )


# Group membership logic -------------------------------------------------------


@pytest.mark.parametrize(
    "groups, expected",
    [
        (["Admin"], True),
        (["Editor"], True),
        (["Viewer"], True),
        (["AMPAdmin"], False),
        ([], False),
    ],
)
def test_admin_satisfies_viewer_tier(groups, expected):
    """Admin > Editor > Viewer is enforced in code, not by Authentik overlap."""
    assert (
        permissions.authorize_groups(
            {"groups": groups}, require_any=["Admin", "Editor", "Viewer"]
        )
        is expected
    )


@pytest.mark.parametrize(
    "groups, expected",
    [
        (["Admin"], True),
        (["Editor"], False),
        (["Viewer"], False),
    ],
)
def test_admin_tier_does_not_accept_lower_roles(groups, expected):
    assert (
        permissions.authorize_groups({"groups": groups}, require_any=["Admin"])
        is expected
    )


def test_role_families_stay_orthogonal():
    """General Admin confers nothing in the AMP or Lexicon families."""
    payload = {"groups": ["Admin"]}
    assert not permissions.authorize_groups(
        payload, require_any=["AMPAdmin", "AMPEditor", "AMPViewer"]
    )
    assert not permissions.authorize_groups(
        payload, require_any=["LexiconAdmin", "LexiconEditor"]
    )


def test_require_all_demands_every_group():
    assert permissions.authorize_groups(
        {"groups": ["Admin", "AMPAdmin"]}, require_all=["Admin", "AMPAdmin"]
    )
    assert not permissions.authorize_groups(
        {"groups": ["Admin"]}, require_all=["Admin", "AMPAdmin"]
    )


def test_missing_groups_claim_denies():
    """A token with no `groups` claim must not satisfy a role requirement."""
    assert not permissions.authorize_groups({}, require_any=["Viewer"])
    assert not permissions.authorize_groups({"groups": None}, require_any=["Viewer"])


# Bypass configuration guard ---------------------------------------------------


@pytest.fixture
def auth_env(monkeypatch):
    """Set MODE and AUTHENTIK_DISABLE_AUTHENTICATION for one test."""

    def _set(mode, disabled):
        monkeypatch.setenv("MODE", mode)
        monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", disabled)

    return _set


@pytest.mark.parametrize("mode", ["production", "staging", "", "Development"])
def test_bypass_outside_development_refuses_to_boot(auth_env, mode):
    """The bypass is honored in development only.

    The old guard only rejected MODE=="production", so a deploy with MODE
    unset served every endpoint anonymously and said nothing about it.
    """
    auth_env(mode, "1")
    with pytest.raises(permissions.AuthConfigurationError) as exc:
        permissions.assert_auth_configuration()
    assert "AUTHENTIK_DISABLE_AUTHENTICATION" in str(exc.value)


def test_bypass_allowed_in_development(auth_env):
    auth_env("development", "1")
    permissions.assert_auth_configuration()


@pytest.mark.parametrize("mode", ["production", "staging", "", "development"])
def test_any_mode_boots_with_auth_enabled(auth_env, mode):
    auth_env(mode, "0")
    permissions.assert_auth_configuration()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True),
        ("0", False),
        ("", False),
        ("true", True),
        ("TRUE", True),
        ("on", True),
        ("no", False),
        ("garbage", False),
    ],
)
def test_authentication_disabled_parsing(monkeypatch, raw, expected):
    """A non-numeric value must not crash the guard into a bypass."""
    monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", raw)
    assert permissions.authentication_disabled() is expected


def test_authentication_disabled_defaults_to_enforcing(monkeypatch):
    monkeypatch.delenv("AUTHENTIK_DISABLE_AUTHENTICATION", raising=False)
    assert permissions.authentication_disabled() is False


def test_mode_is_read_fresh_from_environment(monkeypatch):
    """settings.mode used to be an import-time snapshot, so whether MODE was
    visible depended on which module called load_dotenv() first."""
    from core.settings import settings

    monkeypatch.setenv("MODE", "sentinel-mode")
    assert settings.mode == "sentinel-mode"


# JWKS caching -----------------------------------------------------------------


def test_jwks_cache_expires(monkeypatch):
    """A TTL'd cache, so an Authentik key rotation does not require a redeploy.

    The cache was an unbounded lru_cache: once a rotation invalidated the
    cached keys every request 401'd with "Invalid signing key" until the
    process restarted.
    """
    permissions.reset_jwks_cache()
    monkeypatch.setenv("AUTHENTIK_URL", "https://authentik.example/application/o/x/")
    monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", "0")

    fetches = []

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"keys": [{"kid": f"k{len(fetches)}"}]}

    def _fake_get(url, **kwargs):
        fetches.append(url)
        return _Resp()

    monkeypatch.setattr(permissions.httpx, "get", _fake_get)

    clock = {"now": 1000.0}
    monkeypatch.setattr(permissions.time, "monotonic", lambda: clock["now"])

    permissions.get_jwks()
    permissions.get_jwks()
    assert len(fetches) == 1, "within the TTL the cached document is reused"
    assert fetches[0] == "https://authentik.example/application/o/x/jwks/"

    clock["now"] += permissions.JWKS_TTL_SECONDS + 1
    permissions.get_jwks()
    assert len(fetches) == 2, "past the TTL the document is refetched"

    permissions.reset_jwks_cache()


def test_jwks_not_fetched_when_bypass_active(monkeypatch):
    permissions.reset_jwks_cache()
    monkeypatch.setenv("AUTHENTIK_URL", "https://authentik.example/application/o/x/")
    monkeypatch.setenv("AUTHENTIK_DISABLE_AUTHENTICATION", "1")

    def _explode(*args, **kwargs):
        raise AssertionError("JWKS must not be fetched while auth is bypassed")

    monkeypatch.setattr(permissions.httpx, "get", _explode)
    assert permissions.get_jwks() == {}


def test_accepted_issuers_covers_both_slash_spellings(monkeypatch):
    """The `iss` claim is now verified; operators configure AUTHENTIK_URL with
    and without a trailing slash, so both spellings must be accepted."""
    monkeypatch.setenv("AUTHENTIK_URL", "https://authentik.example/application/o/x/")
    assert set(permissions._accepted_issuers()) == {
        "https://authentik.example/application/o/x",
        "https://authentik.example/application/o/x/",
    }

    monkeypatch.setenv("AUTHENTIK_URL", "https://authentik.example/application/o/x")
    assert set(permissions._accepted_issuers()) == {
        "https://authentik.example/application/o/x",
        "https://authentik.example/application/o/x/",
    }


def test_accepted_issuers_empty_when_unconfigured(monkeypatch):
    """Empty tuple, which _decode() passes to jose as issuer=None."""
    monkeypatch.delenv("AUTHENTIK_URL", raising=False)
    assert permissions._accepted_issuers() == ()


def test_dead_scope_parameter_is_gone():
    """`scope=` was never used and was wrong if it had been: the OIDC scope
    claim is a space-delimited string, so `s in payload["scope"]` was substring
    matching."""
    import inspect

    assert "scope" not in inspect.signature(permissions.authenticated).parameters


# ============= EOF =============================================
