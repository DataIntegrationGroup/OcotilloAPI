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
Rules for personal API keys: token shape, digesting, expiry, usability.

Plain functions over plain values, per ADR4 -- no database, no HTTP. The
authentication path that uses these runs in raw ASGI middleware
(core/internal_ogc_auth.py) where neither a Session nor a Request is in scope,
so keeping the rules here is what makes them testable at all.

See docs/api-key-management.md.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

# Distinguishes an Ocotillo key from an Authentik JWT at a glance, and matches
# the token the settings page in OcotilloUI already generates locally.
TOKEN_PREFIX = "ocot"
TOKEN_SEPARATOR = "_"

# Bytes of entropy in the random half. 32 bytes -> a 43-character urlsafe
# string. This is why the stored digest is unsalted SHA-256 rather than a
# password KDF: there is no dictionary to attack at this entropy, and
# verification stays a single indexed lookup instead of one KDF invocation per
# candidate row. See docs/api-key-management.md.
TOKEN_ENTROPY_BYTES = 32

# Characters of the token shown in the list view, after the prefix. Enough to
# tell two keys apart, not enough to use.
PREVIEW_HEAD = len(TOKEN_PREFIX) + 6
PREVIEW_TAIL = 4
PREVIEW_ELLIPSIS = "…"

# Every key expires. 365 days is both the default and the ceiling -- there is
# no way to ask for a key that outlives it. A lifetime this long is a backstop
# against keys nobody remembers holding (a decommissioned laptop, someone who
# left), not a security control; the control is revocation, which is immediate
# because the keys live in a table rather than in a deploy-time environment
# variable.
DEFAULT_LIFETIME = timedelta(days=365)
MAX_LIFETIME = DEFAULT_LIFETIME

# How stale `last_used_at` is allowed to get before a request pays for a write.
# Desktop GIS clients page through `items`, so writing on every request would
# turn one map refresh into dozens of writes to the same row.
LAST_USED_RESOLUTION = timedelta(minutes=15)

DEFAULT_NAME = "Untitled key"
MAX_NAME_LENGTH = 255

# The only scope v1 issues. A key buys access to the /ogcapi-internal mount and
# nothing else. Deliberately a value rather than a nullable "all" -- widening
# later should be a new member here, not a migration.
SCOPE_OGC_INTERNAL = "ogc_internal"


class ApiKeyError(ValueError):
    """Base for API key rule violations.

    Subclasses ValueError for the same reason the other domain errors do: the
    callers treat a ValueError as a validation failure rather than a fault.
    """


def generate_token() -> str:
    """Return a fresh key: the prefix, then 32 bytes of CSPRNG output."""
    return (
        f"{TOKEN_PREFIX}{TOKEN_SEPARATOR}{secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)}"
    )


def digest_token(token: str) -> str:
    """SHA-256 hex of `token`.

    Same encoding as the operator-issued digests in INTERNAL_OGC_API_KEYS, so
    both credential sources compare identically.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def digests_equal(presented: str, stored: str) -> bool:
    """Constant-time digest comparison.

    The database lookup is by digest and therefore already constant-ish, but a
    caller that has loaded a row by some other means still needs this.
    """
    return hmac.compare_digest(presented, stored)


def preview_token(token: str) -> str:
    """The fragment shown in the list view once the token itself is gone.

    Mirrors `previewOfToken` in OcotilloUI's src/utils/apiKeys.ts so a key
    generated before the backend existed still renders the same way.
    """
    return f"{token[:PREVIEW_HEAD]}{PREVIEW_ELLIPSIS}{token[-PREVIEW_TAIL:]}"


def looks_like_api_key(secret: str) -> bool:
    """Whether `secret` is shaped like one of our keys.

    Lets the authentication path skip a database round trip for a credential
    that is plainly an Authentik JWT. A false positive costs one indexed miss,
    so this checks the prefix only and does not try to validate the body.
    """
    return secret.startswith(f"{TOKEN_PREFIX}{TOKEN_SEPARATOR}")


def normalize_name(name: str | None) -> str:
    """Trim a user-supplied key name, falling back to a placeholder.

    An empty name is not an error: the UI's rename dialog can submit one, and a
    key with a blank label is still a working key. Matches `createApiKey` in
    OcotilloUI's src/utils/apiKeys.ts.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        return DEFAULT_NAME
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ApiKeyError(f"Key name must be {MAX_NAME_LENGTH} characters or fewer.")
    return cleaned


def expiry_for(created_at: datetime, lifetime: timedelta | None = None) -> datetime:
    """When a key created at `created_at` stops working.

    `lifetime` is a caller's request for something shorter; anything longer is
    clamped to MAX_LIFETIME rather than rejected, so asking for ten years
    quietly gets the ceiling instead of a 422 the UI has to explain.
    """
    if lifetime is None:
        return created_at + DEFAULT_LIFETIME
    if lifetime <= timedelta(0):
        raise ApiKeyError("Key lifetime must be positive.")
    return created_at + min(lifetime, MAX_LIFETIME)


def is_expired(expires_at: datetime | None, now: datetime) -> bool:
    """Whether `expires_at` has passed.

    A NULL `expires_at` reads as expired, not as immortal. The column is NOT
    NULL, so NULL means a row written outside the create path -- and a
    credential of unknown provenance should fail closed.
    """
    if expires_at is None:
        return True
    return expires_at <= now


def is_usable(
    revoked_at: datetime | None, expires_at: datetime | None, now: datetime
) -> bool:
    """Whether a key in this state may authenticate a request."""
    return revoked_at is None and not is_expired(expires_at, now)


def should_touch_last_used(last_used_at: datetime | None, now: datetime) -> bool:
    """Whether this request should pay for a `last_used_at` write."""
    if last_used_at is None:
        return True
    return now - last_used_at >= LAST_USED_RESOLUTION


# ============= EOF =============================================
