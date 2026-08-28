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
"""
Authenticating a presented secret against the api_key table.

The rules live in domain/api_key.py; this is the part that needs a Session.
Called from core/internal_ogc_auth.py, which is raw ASGI middleware and
therefore opens its own short-lived session rather than receiving one from
Depends().

See docs/api-key-management.md.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.api_key import ApiKey
from domain.api_key import (
    digest_token,
    is_usable,
    looks_like_api_key,
    should_touch_last_used,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiKeyPrincipal:
    """Who a valid key says the caller is.

    Deliberately not a decoded-JWT-shaped dict: a key is not an identity
    assertion from Authentik, and code downstream should not be able to treat
    the two interchangeably by accident.
    """

    id: int
    name: str
    scope: str
    owner_sub: str
    owner_name: str | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def resolve_api_key(
    session: Session, secret: str, *, now: datetime | None = None
) -> ApiKeyPrincipal | None:
    """Return the principal for `secret`, or None if it is not a usable key.

    None covers every failure the caller treats identically -- wrong shape,
    unknown digest, revoked, expired. The caller falls through to the JWT path
    on None, so distinguishing them here would only leak which one it was.

    Also refreshes `last_used_at`, at most once per
    domain.api_key.LAST_USED_RESOLUTION.
    """
    if not looks_like_api_key(secret):
        # Plainly an Authentik JWT (or junk). Skip the round trip.
        return None

    now = now or _utcnow()

    key = session.scalars(
        select(ApiKey).where(ApiKey.token_digest == digest_token(secret))
    ).one_or_none()
    if key is None:
        return None

    if not is_usable(key.revoked_at, key.expires_at, now):
        return None

    if should_touch_last_used(key.last_used_at, now):
        key.last_used_at = now
        session.commit()

    return ApiKeyPrincipal(
        id=key.id,
        name=key.name,
        scope=key.scope,
        owner_sub=key.owner_sub,
        owner_name=key.owner_name,
    )


def resolve_api_key_in_new_session(secret: str) -> ApiKeyPrincipal | None:
    """resolve_api_key() with a session of its own, for callers outside FastAPI.

    The session is opened and closed before this returns. It must not be held
    across the middleware's downstream `await`: /ogcapi-internal streams
    paginated GeoJSON up to `max_items: 10000`, and a session kept open for the
    body would pin a pool connection for the whole response.

    A database failure returns None rather than raising, so the mount degrades
    to bearer-JWT-only instead of 500ing for everyone when the pool is
    exhausted or the database is briefly unreachable.
    """
    if not looks_like_api_key(secret):
        return None

    from db.engine import session_ctx

    try:
        with session_ctx() as session:
            return resolve_api_key(session, secret)
    except Exception:
        logger.exception(
            "api key lookup failed; falling back to bearer-token authentication",
            extra={"event": "api_key_lookup_failed"},
        )
        return None


# ============= EOF =============================================
