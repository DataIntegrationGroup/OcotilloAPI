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
services/access_admin.py

Writes to the access-control tables: register a destination, grant, revoke,
record a landowner's consent, withdraw it.

Every write lands an ``authorization_audit`` row in the same transaction. That
is the point of the module: there is no path that changes who may see what and
leaves no trace, because the question after an incident is "who granted that,
and when" (ADR5, 4.3).

Rules live in ``domain/access.py`` and are checked before the row is written,
so an unevaluable grant -- no data type, a global grant with a scope id --
cannot reach the table. Domain errors subclass ValueError; the routes turn
them into 422s.
"""

from datetime import date, datetime, timezone

from db.authorization_audit import (
    AuthorizationAudit,
    CONSENT_RECORDED,
    CONSENT_REVOKED,
    DESTINATION_REGISTERED,
    GRANT_CREATED,
    GRANT_REVOKED,
)
from db.destination import Destination
from db.permission_grant import PermissionGrant
from db.publication_consent import PublicationConsent
from domain.access import require_forward_range, validate_grant

# Used when the caller's token carries no subject -- the development bypass,
# or a test override. Recorded rather than left null: "we do not know who"
# is itself worth knowing when reading the log back.
UNKNOWN_ACTOR = "unknown"


class AlreadyRevoked(ValueError):
    """Raised when revoking something that is already revoked."""


def actor_from_payload(payload) -> str:
    """The identifier to record as having done this."""
    if not isinstance(payload, dict):
        return UNKNOWN_ACTOR
    return str(payload.get("sub") or payload.get("preferred_username") or UNKNOWN_ACTOR)


def _audit(session, actor, event_type, subject_table, subject_id, detail):
    session.add(
        AuthorizationAudit(
            event_type=event_type,
            actor=actor,
            subject_table=subject_table,
            subject_id=subject_id,
            detail=detail,
        )
    )


def register_destination(
    session,
    actor: str,
    slug: str,
    name: str,
    destination_kind: str,
    description: str = None,
) -> Destination:
    destination = Destination(
        slug=slug,
        name=name,
        destination_kind=destination_kind,
        description=description,
        active=True,
    )
    session.add(destination)
    session.flush()
    _audit(
        session,
        actor,
        DESTINATION_REGISTERED,
        Destination.__tablename__,
        destination.id,
        {"slug": slug, "name": name, "destination_kind": destination_kind},
    )
    session.commit()
    session.refresh(destination)
    return destination


def create_grant(
    session,
    actor: str,
    principal_type: str,
    principal_id: str,
    capability: str,
    scope_type: str,
    scope_id: int,
    data_type: str,
    starts_at: date,
    ends_at: date = None,
    reason: str = None,
    ui_surface: str = None,
) -> PermissionGrant:
    validate_grant(
        principal_type=principal_type,
        capability=capability,
        scope_type=scope_type,
        scope_id=scope_id,
        data_type=data_type,
        starts_at=starts_at,
        ends_at=ends_at,
        ui_surface=ui_surface,
    )

    grant = PermissionGrant(
        principal_type=principal_type,
        principal_id=principal_id,
        capability=capability,
        scope_type=scope_type,
        scope_id=scope_id,
        data_type=data_type,
        ui_surface=ui_surface,
        starts_at=starts_at,
        ends_at=ends_at,
        granted_by=actor,
        reason=reason,
    )
    session.add(grant)
    session.flush()
    _audit(
        session,
        actor,
        GRANT_CREATED,
        PermissionGrant.__tablename__,
        grant.id,
        {
            "principal_type": principal_type,
            "principal_id": principal_id,
            "capability": capability,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "data_type": data_type,
            "ui_surface": ui_surface,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "reason": reason,
        },
    )
    session.commit()
    session.refresh(grant)
    return grant


def revoke_grant(session, actor: str, grant: PermissionGrant) -> PermissionGrant:
    """Revoke now. Effective at the next read, never backdated."""
    if grant.revoked_at is not None:
        raise AlreadyRevoked(f"grant {grant.id} was already revoked.")

    grant.revoked_at = datetime.now(timezone.utc)
    grant.revoked_by = actor
    _audit(
        session,
        actor,
        GRANT_REVOKED,
        PermissionGrant.__tablename__,
        grant.id,
        {
            "principal_type": grant.principal_type,
            "principal_id": grant.principal_id,
            "capability": grant.capability,
            "data_type": grant.data_type,
        },
    )
    session.commit()
    session.refresh(grant)
    return grant


def record_consent(
    session,
    actor: str,
    thing_id: int,
    destination_id: int,
    data_type: str,
    starts_at: date,
    ends_at: date = None,
    contact_id: int = None,
    notes: str = None,
) -> PublicationConsent:
    """Record that an owner agreed to publish this data type here."""
    require_forward_range(starts_at, ends_at)

    consent = PublicationConsent(
        thing_id=thing_id,
        destination_id=destination_id,
        data_type=data_type,
        contact_id=contact_id,
        recorded_by=actor,
        notes=notes,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    session.add(consent)
    session.flush()
    _audit(
        session,
        actor,
        CONSENT_RECORDED,
        PublicationConsent.__tablename__,
        consent.id,
        {
            "thing_id": thing_id,
            "destination_id": destination_id,
            "data_type": data_type,
            "contact_id": contact_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
        },
    )
    session.commit()
    session.refresh(consent)
    return consent


def revoke_consent(
    session, actor: str, consent: PublicationConsent
) -> PublicationConsent:
    """Stop offering this.

    Not a recall: copies a harvester already took live in someone else's
    system, and the owner should be told that rather than promised otherwise.
    """
    if consent.revoked_at is not None:
        raise AlreadyRevoked(f"consent {consent.id} was already revoked.")

    consent.revoked_at = datetime.now(timezone.utc)
    consent.revoked_by = actor
    _audit(
        session,
        actor,
        CONSENT_REVOKED,
        PublicationConsent.__tablename__,
        consent.id,
        {
            "thing_id": consent.thing_id,
            "destination_id": consent.destination_id,
            "data_type": consent.data_type,
        },
    )
    session.commit()
    session.refresh(consent)
    return consent


# ============= EOF =============================================
