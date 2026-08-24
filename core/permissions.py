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
import os
import threading
import time
from typing import Optional, List, Sequence, Tuple, Union, cast, Callable

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, OAuth2AuthorizationCodeBearer
from jose import jwt
from jose.exceptions import JWTError
from jwt.algorithms import RSAAlgorithm
from starlette.requests import Request
from starlette.responses import Response

from core.settings import settings

ALGORITHMS = ["RS256"]

# The only MODE in which AUTHENTIK_DISABLE_AUTHENTICATION=1 is honored.
# assert_auth_configuration() refuses to boot anywhere else, so a box with an
# unset or mislabeled MODE can never come up with authentication switched off.
BYPASS_ALLOWED_MODE = "development"

# How long a fetched JWKS document is trusted. Authentik rotates its signing
# keys; the cache used to be an unbounded lru_cache, so a rotation 401'd every
# request until the process was redeployed. get_public_key() also forces one
# refresh on an unrecognized `kid`, which covers rotations inside the window.
JWKS_TTL_SECONDS = int(os.environ.get("AUTHENTIK_JWKS_TTL_SECONDS", "3600"))


def _issuer() -> str:
    """Authentik issuer URL, read lazily so it survives late load_dotenv()."""
    return (os.environ.get("AUTHENTIK_URL") or "").strip()


def _accepted_issuers() -> Tuple[str, ...]:
    """Issuer values accepted for the `iss` claim.

    Authentik's issuer is the provider URL, which operators configure with or
    without a trailing slash depending on where they copied it from. Accept
    both spellings rather than making token validation depend on that.
    """
    issuer = _issuer()
    if not issuer:
        return ()
    return (issuer.rstrip("/"), issuer.rstrip("/") + "/")


def authentication_disabled() -> bool:
    """Whether the development authentication bypass is switched on.

    Read fresh from the environment on every call. This used to be an
    import-time snapshot (`auth_disabled`) that the per-request check in
    authenticated() did not share: flipping the variable after import left
    JWKS fetching disabled while token verification stayed live, so every
    request failed with "Invalid signing key" instead of either enforcing or
    bypassing cleanly.
    """
    raw = (os.environ.get("AUTHENTIK_DISABLE_AUTHENTICATION") or "0").strip()
    try:
        return bool(int(raw))
    except ValueError:
        return raw.lower() in {"true", "yes", "on"}


class AuthConfigurationError(RuntimeError):
    """Raised at startup when the auth bypass is enabled outside development."""


def bypass_misconfiguration_detail() -> str:
    return (
        "AUTHENTIK_DISABLE_AUTHENTICATION is enabled but MODE is "
        f"{settings.mode or '<unset>'!r}. The bypass is only permitted when "
        f"MODE={BYPASS_ALLOWED_MODE!r}. Set "
        "AUTHENTIK_DISABLE_AUTHENTICATION=0, or set MODE=development."
    )


def assert_auth_configuration() -> None:
    """Fail fast when the app is configured to serve traffic without auth.

    Called from core.factory.create_api_app() after load_dotenv(). The old
    guard was per-request and keyed on `settings.mode == "production"`, so a
    deploy with MODE unset served every endpoint anonymously and logged
    nothing. Two independent variables had to be right; now a wrong one stops
    the process at boot.
    """
    if authentication_disabled() and settings.mode != BYPASS_ALLOWED_MODE:
        raise AuthConfigurationError(bypass_misconfiguration_detail())


_jwks_lock = threading.Lock()
_jwks_cache: dict = {"payload": None, "fetched_at": 0.0}


def reset_jwks_cache() -> None:
    """Drop the cached JWKS. Test hook and manual-invalidation escape hatch."""
    with _jwks_lock:
        _jwks_cache["payload"] = None
        _jwks_cache["fetched_at"] = 0.0


def get_jwks(force_refresh: bool = False) -> dict:
    if not _issuer() or authentication_disabled():
        return {}

    if not force_refresh:
        with _jwks_lock:
            cached = _jwks_cache["payload"]
            age = time.monotonic() - _jwks_cache["fetched_at"]
            if cached is not None and age < JWKS_TTL_SECONDS:
                return cached

    resp = httpx.get(f"{_issuer().rstrip('/')}/jwks/", timeout=10.0)
    resp.raise_for_status()
    payload = resp.json()

    with _jwks_lock:
        _jwks_cache["payload"] = payload
        _jwks_cache["fetched_at"] = time.monotonic()
    return payload


def _find_signing_key(jwks: dict, kid: Optional[str]) -> Optional[dict]:
    if not kid:
        return None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def get_public_key(token):
    kid = jwt.get_unverified_header(token).get("kid")

    key = _find_signing_key(get_jwks(), kid)
    if key is None:
        # Unknown kid: Authentik may have rotated inside the TTL window.
        # Refetch once before rejecting an otherwise valid token.
        key = _find_signing_key(get_jwks(force_refresh=True), kid)
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid signing key")
    return RSAAlgorithm.from_jwk(key)


TokenType = Union[str, HTTPAuthorizationCredentials]
scheme = OAuth2AuthorizationCodeBearer(
    # authorizationUrl=f"{settings.FIEF_URL}/authorize",
    # tokenUrl=f"{settings.FIEF_URL}/api/token",
    authorizationUrl=os.environ.get("AUTHENTIK_AUTHORIZE_URL", ""),
    tokenUrl=os.environ.get("AUTHENTIK_TOKEN_URL", ""),
    scopes={"openid": "openid", "offline_access": "offline_access"},
    auto_error=False,
)


def authorize_groups(
    payload: dict,
    require_all: Optional[Sequence[str]] = None,
    require_any: Optional[Sequence[str]] = None,
) -> bool:
    """Check a decoded token's `groups` claim against a group requirement.

    `require_all` demands every listed group; `require_any` demands at least
    one. Role tiers in core/dependencies.py use `require_any` so that an Admin
    satisfies an Editor- or Viewer-gated route. The old check was all-of only,
    which meant the documented Admin > Editor > Viewer hierarchy existed
    nowhere in code -- it worked solely because operators happened to grant
    overlapping groups in Authentik, and an Admin without the Viewer group got
    a 403 on every read.
    """
    groups = payload.get("groups") or []
    if require_all and not all(group in groups for group in require_all):
        return False
    if require_any and not any(group in groups for group in require_any):
        return False
    return True


def authenticated(
    optional: bool = False,
    permissions: Optional[List[str]] = None,
    any_of: Optional[List[str]] = None,
):
    """Build a FastAPI dependency enforcing a bearer token and group membership.

    `permissions` requires every listed Authentik group, `any_of` requires at
    least one. Returns the decoded token payload on success so endpoints can
    read claims; returns True when the development bypass is active.
    """

    def _authenticated(
        request: Request,
        response: Response,
        token: TokenType = Depends(cast(Callable, scheme)),
    ):
        if authentication_disabled():
            # assert_auth_configuration() already rejected this combination at
            # startup; this is the belt for a variable flipped at runtime.
            if settings.mode != BYPASS_ALLOWED_MODE:
                raise HTTPException(
                    status_code=status.HTTP_424_FAILED_DEPENDENCY,
                    detail=bypass_misconfiguration_detail(),
                )
            return True

        if not token:
            if optional:
                return True
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )

        # Decoded once and reused. The previous flow decoded the JWT twice per
        # request: verify_token() decoded to read groups, then the caller
        # decoded again to build the return value.
        payload = _get_token_payload(token)

        if not authorize_groups(payload, require_all=permissions, require_any=any_of):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )

        return payload

    return _authenticated


def _decode(token: str) -> dict:
    """Verify signature, audience, and issuer, returning the claims."""
    return jwt.decode(
        token,
        get_public_key(token),
        algorithms=ALGORITHMS,
        audience=os.environ.get("AUTHENTIK_CLIENT_ID"),  # Authentik application
        issuer=_accepted_issuers() or None,
    )


def _get_token_payload(token: str) -> dict:
    try:
        return _decode(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


class TokenInvalid(Exception):
    """Raised by decode_token_payload() for any JWT verification failure.

    Not an HTTPException: this is called from raw ASGI middleware
    (core/internal_ogc_auth.py), which has no FastAPI exception handler
    watching, so raising HTTPException there would just be an unhandled
    exception rather than the intended response.
    """


# Required Authentik group for the authenticated internal OGC mount
# (/ogcapi-internal). Not Depends()-shaped like the roles above -- see the
# cross-reference note in core/dependencies.py for why it still lives here.
INTERNAL_OGC_GROUP = "OGCInternal"


def decode_token_payload(token: str) -> dict:
    """Same JWT verification as _get_token_payload (shared _decode helper),
    but raises TokenInvalid instead of HTTPException(401).
    """
    try:
        return _decode(token)
    except (JWTError, HTTPException) as e:
        raise TokenInvalid(str(e)) from e


# ============= EOF =============================================
