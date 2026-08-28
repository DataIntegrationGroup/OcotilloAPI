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
"""
api/access.py

The first tenant of the ADR5 visibility layer.

One router, deliberately small:

* ``/access/grant`` administers internal grants, and ``/access/decision``
  answers "may I, right now?" from ``services/visibility.py`` rather than from
  anything local.
* ``/access/destination`` and ``/access/consent`` administer destinations and
  landowner consent, and ``/access/destination/{slug}/thing`` answers "what
  does this destination get".

The prefix is ``/access`` rather than ``/publication`` because
``api/publication.py`` is already the bibliography -- citations, not consent.

Nothing here changes what an existing endpoint returns. The layer is proved
end to end behind one service before it is put behind all of them (ADR5, A.6).
Every route is authorized: administration is Admin, reading is Viewer.
"""

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED

from core.dependencies import (
    admin_dependency,
    session_dependency,
    viewer_dependency,
)
from db.destination import Destination
from db.permission_grant import PermissionGrant
from db.publication_consent import PublicationConsent
from schemas.access import (
    AccessDecision,
    CreateDestination,
    CreatePermissionGrant,
    CreatePublicationConsent,
    DestinationResponse,
    PermissionGrantResponse,
    PublicationConsentResponse,
    PublishedThing,
)
from services.access_admin import (
    AlreadyRevoked,
    actor_from_payload,
    create_grant,
    record_consent,
    register_destination,
    revoke_consent,
    revoke_grant,
)
from services.exceptions_helper import PydanticStyleException
from services.visibility import (
    destination_by_slug,
    may,
    principals_from_payload,
    published_things,
)

router = APIRouter(prefix="/access", tags=["access control"])


def _not_found(what: str, value):
    return PydanticStyleException(
        status_code=404,
        detail=[
            {
                "loc": ["path", what],
                "msg": f"No {what} {value!r}.",
                "type": "value_error",
                "input": value,
            }
        ],
    )


def _invalid(field: str, message: str, value):
    return PydanticStyleException(
        status_code=422,
        detail=[
            {
                "loc": ["body", field],
                "msg": message,
                "type": "value_error",
                "input": value,
            }
        ],
    )


# ============= Permission grants =============================================


@router.post(
    "/grant", summary="Create a permission grant", status_code=HTTP_201_CREATED
)
def create_permission_grant(
    payload: CreatePermissionGrant,
    session: session_dependency,
    user: admin_dependency,
) -> PermissionGrantResponse:
    """Grant a principal one capability over one data type within one scope.

    The grant names its data type; there is no wildcard, so a data type added
    later is never covered by this row.
    """
    try:
        grant = create_grant(
            session,
            actor_from_payload(user),
            principal_type=payload.principal_type.value,
            principal_id=payload.principal_id,
            capability=payload.capability.value,
            scope_type=payload.scope_type.value,
            scope_id=payload.scope_id,
            data_type=payload.data_type.value,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
        )
    except ValueError as exception:
        raise _invalid("scope_id", str(exception), payload.scope_id)

    return PermissionGrantResponse.model_validate(grant)


@router.post(
    "/grant/{grant_id}/revocation",
    summary="Revoke a permission grant",
    status_code=HTTP_201_CREATED,
)
def revoke_permission_grant(
    grant_id: int,
    session: session_dependency,
    user: admin_dependency,
) -> PermissionGrantResponse:
    """Revoke now. Effective at the next read, not at the next token refresh."""
    grant = session.get(PermissionGrant, grant_id)
    if grant is None:
        raise _not_found("grant_id", grant_id)

    try:
        grant = revoke_grant(session, actor_from_payload(user), grant)
    except AlreadyRevoked as exception:
        raise _invalid("grant_id", str(exception), grant_id)

    return PermissionGrantResponse.model_validate(grant)


@router.get("/grant", summary="List grants")
def get_permission_grants(
    session: session_dependency,
    user: admin_dependency,
    principal_id: str = Query(
        default=None, description="Authentik subject, role, or key label"
    ),
    capability: str = Query(default=None),
    data_type: str = Query(default=None),
    scope_type: str = Query(default=None),
    include_revoked: bool = Query(default=False),
) -> list[PermissionGrantResponse]:
    """All grants, or a narrower slice of them.

    Every filter is optional, so the bare route is the admin-wide audit view;
    passing ``principal_id`` narrows it to one principal, as before.
    """
    statement = select(PermissionGrant)
    if principal_id is not None:
        statement = statement.where(PermissionGrant.principal_id == principal_id)
    if capability is not None:
        statement = statement.where(PermissionGrant.capability == capability)
    if data_type is not None:
        statement = statement.where(PermissionGrant.data_type == data_type)
    if scope_type is not None:
        statement = statement.where(PermissionGrant.scope_type == scope_type)
    if not include_revoked:
        statement = statement.where(PermissionGrant.revoked_at.is_(None))

    return [
        PermissionGrantResponse.model_validate(row)
        for row in session.execute(statement).scalars()
    ]


@router.get("/decision", summary="Ask the visibility layer about yourself")
def get_access_decision(
    session: session_dependency,
    user: viewer_dependency,
    capability: str = Query(),
    data_type: str = Query(),
    thing_id: int = Query(default=None),
    on_date: date = Query(default=None),
) -> AccessDecision:
    """May the caller do this? Answered by the one visibility layer.

    Default deny: an unrecognized capability or a caller the token says
    nothing about gets False rather than an error, because a question this
    layer cannot answer is not a yes.
    """
    principals = principals_from_payload(user)
    return AccessDecision(
        allowed=may(
            session,
            principals,
            capability=capability,
            data_type=data_type,
            thing_id=thing_id,
            on_date=on_date,
        ),
        capability=capability,
        data_type=data_type,
        thing_id=thing_id,
        principals=[f"{kind}:{identifier}" for kind, identifier in principals],
    )


# ============= Destinations =============================================


@router.post(
    "/destination", summary="Register a destination", status_code=HTTP_201_CREATED
)
def create_destination(
    payload: CreateDestination,
    session: session_dependency,
    user: admin_dependency,
) -> DestinationResponse:
    existing = destination_by_slug(session, payload.slug)
    if existing is not None:
        raise PydanticStyleException(
            status_code=409,
            detail=[
                {
                    "loc": ["body", "slug"],
                    "msg": f"Destination {payload.slug!r} already exists.",
                    "type": "value_error",
                    "input": payload.slug,
                }
            ],
        )

    destination = register_destination(
        session,
        actor_from_payload(user),
        slug=payload.slug,
        name=payload.name,
        destination_kind=payload.destination_kind.value,
        description=payload.description,
    )
    return DestinationResponse.model_validate(destination)


@router.get("/destination", summary="List destinations")
def get_destinations(
    session: session_dependency,
    user: viewer_dependency,
) -> list[DestinationResponse]:
    return [
        DestinationResponse.model_validate(row)
        for row in session.execute(select(Destination).order_by(Destination.slug))
        .scalars()
        .all()
    ]


@router.get("/destination/{slug}/thing", summary="What this destination may read")
def get_published_things(
    slug: str,
    session: session_dependency,
    user: viewer_dependency,
    data_type: str = Query(default=None),
    on_date: date = Query(default=None),
) -> list[PublishedThing]:
    """The destination's view, computed from consent rows at request time.

    A retired destination gets an empty list, and so does one nobody has
    consented to yet: default deny, with no separate "unpublished" state to
    keep in sync.
    """
    destination = destination_by_slug(session, slug)
    if destination is None:
        raise _not_found("slug", slug)

    return [
        PublishedThing(**entry)
        for entry in published_things(
            session, destination, data_type=data_type, on_date=on_date
        )
    ]


# ============= Publication consent =============================================


@router.post(
    "/consent", summary="Record publication consent", status_code=HTTP_201_CREATED
)
def create_publication_consent(
    payload: CreatePublicationConsent,
    session: session_dependency,
    user: admin_dependency,
) -> PublicationConsentResponse:
    """Record that an owner agreed to publish one data type to one destination."""
    destination = destination_by_slug(session, payload.destination_slug)
    if destination is None:
        raise _not_found("destination_slug", payload.destination_slug)

    try:
        consent = record_consent(
            session,
            actor_from_payload(user),
            thing_id=payload.thing_id,
            destination_id=destination.id,
            data_type=payload.data_type.value,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            contact_id=payload.contact_id,
            notes=payload.notes,
        )
    except ValueError as exception:
        raise _invalid("ends_at", str(exception), payload.ends_at)

    return PublicationConsentResponse.model_validate(consent)


@router.post(
    "/consent/{consent_id}/revocation",
    summary="Withdraw publication consent",
    status_code=HTTP_201_CREATED,
)
def revoke_publication_consent(
    consent_id: int,
    session: session_dependency,
    user: admin_dependency,
) -> PublicationConsentResponse:
    """Stop offering it. Copies already harvested are not recalled."""
    consent = session.get(PublicationConsent, consent_id)
    if consent is None:
        raise _not_found("consent_id", consent_id)

    try:
        consent = revoke_consent(session, actor_from_payload(user), consent)
    except AlreadyRevoked as exception:
        raise _invalid("consent_id", str(exception), consent_id)

    return PublicationConsentResponse.model_validate(consent)


@router.get("/consent", summary="List consent for a thing")
def get_publication_consent(
    session: session_dependency,
    user: viewer_dependency,
    thing_id: int = Query(),
    include_revoked: bool = Query(default=False),
) -> list[PublicationConsentResponse]:
    statement = select(PublicationConsent).where(
        PublicationConsent.thing_id == thing_id
    )
    if not include_revoked:
        statement = statement.where(PublicationConsent.revoked_at.is_(None))

    return [
        PublicationConsentResponse.model_validate(row)
        for row in session.execute(statement).scalars()
    ]


# ============= EOF =============================================
