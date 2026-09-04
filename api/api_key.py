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
Personal API keys for /ogcapi-internal.

Every route is gated on `internal_ogc_dependency` -- the OGCInternal group --
rather than on a general role. A key is a pre-authorized stand-in for that
group, so minting one is exactly as privileged as holding it. Gating creation
on a lower tier would let a Viewer issue themselves access to the unfiltered
internal collections.

Every route also filters on the caller's own `sub`. Somebody else's key is a
404, not a 403: whether a given id exists is not the caller's business.

See docs/api-key-management.md.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import select
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from core.dependencies import internal_ogc_dependency, session_dependency
from db.api_key import ApiKey
from domain.api_key import (
    SCOPE_OGC_INTERNAL,
    digest_token,
    expiry_for,
    generate_token,
    is_usable,
    normalize_name,
    preview_token,
)
from schemas.api_key import (
    ApiKeyResponse,
    CreateApiKey,
    NewApiKeyResponse,
    UpdateApiKey,
)
from services.exceptions_helper import PydanticStyleException

router = APIRouter(prefix="/api_key", tags=["api_key"])
logger = logging.getLogger(__name__)

# Who owns a key created while AUTHENTIK_DISABLE_AUTHENTICATION=1. The bypass
# hands the route `True` instead of a token payload, so there is no `sub` to
# own the row. It is only honored when MODE=development (see
# core/permissions.assert_auth_configuration), so this value can never appear
# in a deployed database.
DEVELOPMENT_OWNER = ("development", "development bypass")


def _owner(user) -> tuple[str, str | None]:
    """The (sub, name) that owns keys created by this caller."""
    if isinstance(user, dict):
        return user["sub"], user.get("name")
    return DEVELOPMENT_OWNER


def _owned_key(session, key_id: int, user) -> ApiKey:
    """Load one of the caller's own keys, or 404."""
    owner_sub, _ = _owner(user)
    key = session.scalars(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.owner_sub == owner_sub)
    ).one_or_none()
    if key is None:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "api_key_id"],
                    "msg": f"API key with ID {key_id} not found.",
                    "type": "value_error",
                    "input": {"api_key_id": key_id},
                }
            ],
        )
    return key


# POST =========================================================================
@router.post(
    "",
    summary="Issue a new API key",
    status_code=HTTP_201_CREATED,
)
def create_api_key(
    user: internal_ogc_dependency,
    payload: CreateApiKey,
    session: session_dependency,
) -> NewApiKeyResponse:
    """
    Issue an API key for the calling user.

    The response is the only place the token ever appears. Only its SHA-256
    digest is stored, so it cannot be shown again or recovered -- a client that
    loses it has to issue another key.
    """
    owner_sub, owner_name = _owner(user)
    now = datetime.now(timezone.utc)
    token = generate_token()

    lifetime = (
        timedelta(days=payload.lifetime_days)
        if payload.lifetime_days is not None
        else None
    )

    key = ApiKey(
        token_digest=digest_token(token),
        token_preview=preview_token(token),
        name=normalize_name(payload.name),
        owner_sub=owner_sub,
        owner_name=owner_name,
        scope=SCOPE_OGC_INTERNAL,
        expires_at=expiry_for(now, lifetime),
        created_by_id=owner_sub,
        created_by_name=owner_name,
    )
    session.add(key)
    session.commit()
    session.refresh(key)

    logger.info(
        "api key issued",
        extra={
            "event": "api_key_issued",
            "api_key_id": key.id,
            "api_key_preview": key.token_preview,
        },
    )

    return NewApiKeyResponse(
        **ApiKeyResponse.model_validate(key).model_dump(), token=token
    )


# GET ==========================================================================
@router.get("", summary="List your API keys")
def get_api_keys(
    user: internal_ogc_dependency,
    session: session_dependency,
) -> list[ApiKeyResponse]:
    """
    List the calling user's keys, active first and newest first within each
    group -- the order OcotilloUI's `sortApiKeys` expects.

    Never includes a token. Not paginated: a person holds a handful of keys,
    and a CustomPage envelope would only make the settings card unwrap it.
    """
    owner_sub, _ = _owner(user)
    keys = session.scalars(
        select(ApiKey)
        .where(ApiKey.owner_sub == owner_sub)
        .order_by(ApiKey.revoked_at.is_(None).desc(), ApiKey.created_at.desc())
    ).all()
    return [ApiKeyResponse.model_validate(key) for key in keys]


# PATCH ========================================================================
@router.patch("/{api_key_id}", summary="Rename an API key")
def update_api_key(
    user: internal_ogc_dependency,
    api_key_id: int,
    payload: UpdateApiKey,
    session: session_dependency,
) -> ApiKeyResponse:
    """
    Rename one of the calling user's keys.

    Allowed on a revoked key too. The name is only a label for the person
    reading the list, and being able to annotate a key you have already revoked
    ("laptop, stolen") is worth more than the extra failure mode.
    """
    key = _owned_key(session, api_key_id, user)
    owner_sub, owner_name = _owner(user)

    key.name = normalize_name(payload.name)
    key.updated_by_id = owner_sub
    key.updated_by_name = owner_name
    session.commit()
    session.refresh(key)

    return ApiKeyResponse.model_validate(key)


# DELETE =======================================================================
@router.delete(
    "/{api_key_id}",
    summary="Revoke an API key",
    status_code=HTTP_204_NO_CONTENT,
)
def revoke_api_key(
    user: internal_ogc_dependency,
    api_key_id: int,
    session: session_dependency,
) -> None:
    """
    Revoke one of the calling user's keys. Takes effect on the next request --
    no redeploy, no cache to wait out.

    The row is kept, not deleted: `last_used_at` is the thing you want after
    revoking a key you think was leaked. Revoking twice is a no-op that leaves
    the original revocation time alone rather than moving it forward.
    """
    key = _owned_key(session, api_key_id, user)
    now = datetime.now(timezone.utc)
    owner_sub, owner_name = _owner(user)

    if is_usable(key.revoked_at, key.expires_at, now):
        key.revoked_at = now
        key.updated_by_id = owner_sub
        key.updated_by_name = owner_name
        session.commit()
        logger.info(
            "api key revoked",
            extra={
                "event": "api_key_revoked",
                "api_key_id": key.id,
                "api_key_preview": key.token_preview,
            },
        )
    elif key.revoked_at is None:
        # Expired but never revoked. Stamp it so the list stops showing it as
        # merely aged and the reason it stopped working is unambiguous.
        key.revoked_at = now
        key.updated_by_id = owner_sub
        key.updated_by_name = owner_name
        session.commit()


# ============= EOF =============================================
