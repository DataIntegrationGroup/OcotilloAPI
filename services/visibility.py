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
services/visibility.py

The one place that answers "what may this principal see, and what has this
destination been given" (ADR5, Part IV).

Every consumer asks here. Not the public API filtering one way and a harvester
view another: three services filtering independently give three subtly
different answers to "is this published", and an outside party finds the
difference first. That is not hypothetical in this repository -- migration
baba91fe5e83 fixed exactly that between two OGC views.

This module loads rows and hands them to ``domain/access.py``, which holds the
rules. It decides nothing itself.

Grants are read at request time and never cached here. ADR5 A.5 allows a short
per-principal cache with explicit invalidation on revoke; an unbounded one
would silently defeat the immediate-revocation promise, so the first version
has none.
"""

from datetime import date

from sqlalchemy import select

from db.destination import Destination
from db.group import GroupThingAssociation
from db.permission_grant import PermissionGrant
from db.publication_consent import PublicationConsent
from db.thing import Thing
from domain.access import (
    AccessRequest,
    Consent,
    Grant,
    PRINCIPAL_ROLE,
    PRINCIPAL_USER,
    any_grant_allows,
    consent_covers,
)

# Claims carrying the caller's identity and their Authentik groups.
SUBJECT_CLAIM = "sub"
GROUPS_CLAIM = "groups"


def principals_from_payload(payload) -> tuple[tuple[str, str], ...]:
    """Every identity a caller presents, as (principal_type, principal_id).

    A caller is their subject *and* each role they hold, because a grant may
    name any of them.

    The development bypass returns ``True`` rather than a token payload, and an
    anonymous caller has no payload at all. Both yield no principals, which
    means default deny: the bypass turns off authentication, not authorization.
    """
    if not isinstance(payload, dict):
        return ()

    principals = []
    subject = payload.get(SUBJECT_CLAIM)
    if subject:
        principals.append((PRINCIPAL_USER, str(subject)))
    for group in payload.get(GROUPS_CLAIM) or []:
        principals.append((PRINCIPAL_ROLE, str(group)))
    return tuple(principals)


def group_ids_for_thing(session, thing_id: int) -> tuple[int, ...]:
    """The groups a thing belongs to, which is what a project grant reaches."""
    if thing_id is None:
        return ()
    rows = session.execute(
        select(GroupThingAssociation.group_id).where(
            GroupThingAssociation.thing_id == thing_id
        )
    ).all()
    return tuple(row[0] for row in rows)


def load_grants(session, principals: tuple[tuple[str, str], ...]) -> list[Grant]:
    """Live and expired grants for these principals, as domain values.

    Expired and revoked rows are loaded rather than filtered in SQL so the
    date rule lives in one place -- ``domain.access.is_active`` -- instead of
    being restated as a WHERE clause that can drift from it.
    """
    if not principals:
        return []

    principal_ids = {principal_id for _, principal_id in principals}
    rows = session.execute(
        select(PermissionGrant).where(PermissionGrant.principal_id.in_(principal_ids))
    ).scalars()

    return [
        Grant(
            principal_type=row.principal_type,
            principal_id=row.principal_id,
            capability=row.capability,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
            data_type=row.data_type,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


def may(
    session,
    principals: tuple[tuple[str, str], ...],
    capability: str,
    data_type: str,
    thing_id: int = None,
    on_date: date = None,
) -> bool:
    """May these principals do this, to this data type, at this thing?

    Default deny. No principals, no grants, or nothing matching is a no.
    """
    request = AccessRequest(
        capability=capability,
        data_type=data_type,
        principals=tuple(principals),
        thing_id=thing_id,
        group_ids=group_ids_for_thing(session, thing_id),
    )
    return any_grant_allows(
        load_grants(session, request.principals), request, on_date or date.today()
    )


def destination_by_slug(session, slug: str) -> Destination | None:
    return session.execute(
        select(Destination).where(Destination.slug == slug)
    ).scalar_one_or_none()


def _consent_rows(session, destination_id: int, data_type: str = None):
    statement = select(PublicationConsent).where(
        PublicationConsent.destination_id == destination_id
    )
    if data_type:
        statement = statement.where(PublicationConsent.data_type == data_type)
    return session.execute(statement).scalars().all()


def published_data_types(
    session, destination: Destination, thing_id: int, on_date: date = None
) -> list[str]:
    """Data types this destination may read for one thing."""
    if not destination.active:
        return []

    on_date = on_date or date.today()
    return sorted(
        {
            row.data_type
            for row in _consent_rows(session, destination.id)
            if row.thing_id == thing_id
            and consent_covers(
                Consent(
                    thing_id=row.thing_id,
                    destination_id=row.destination_id,
                    data_type=row.data_type,
                    starts_at=row.starts_at,
                    ends_at=row.ends_at,
                    revoked_at=row.revoked_at,
                ),
                thing_id,
                destination.id,
                row.data_type,
                on_date,
            )
        }
    )


def published_things(
    session, destination: Destination, data_type: str = None, on_date: date = None
) -> list[dict]:
    """What this destination gets: one entry per thing, with its data types.

    A retired destination gets nothing, without the caller having to remember
    to check.
    """
    if not destination.active:
        return []

    on_date = on_date or date.today()
    by_thing: dict[int, set] = {}
    for row in _consent_rows(session, destination.id, data_type):
        covered = consent_covers(
            Consent(
                thing_id=row.thing_id,
                destination_id=row.destination_id,
                data_type=row.data_type,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                revoked_at=row.revoked_at,
            ),
            row.thing_id,
            destination.id,
            row.data_type,
            on_date,
        )
        if covered:
            by_thing.setdefault(row.thing_id, set()).add(row.data_type)

    if not by_thing:
        return []

    names = dict(
        session.execute(
            select(Thing.id, Thing.name).where(Thing.id.in_(by_thing.keys()))
        ).all()
    )
    return [
        {
            "thing_id": thing_id,
            "name": names.get(thing_id),
            "data_types": sorted(data_types),
        }
        for thing_id, data_types in sorted(by_thing.items())
    ]


# ============= EOF =============================================
