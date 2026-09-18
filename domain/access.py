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
"""
Access-control rules from ADR5, as plain functions over plain values.

Two questions, one grammar:

* May this principal exercise this capability within this scope?
  (``permission_grant`` -- institutional trust, decided per person.)
* Did the owner agree to publish this data type of this well to this
  destination? (``publication_consent`` -- landowner consent, decided per well.)

Two record types with separate governance, evaluated the same way. The rules
live here so they can be exercised without a database; ``services/visibility.py``
loads the rows and asks.

Three invariants this module exists to keep:

* **Default deny.** No grant means no. An empty sequence answers False, and
  every helper returns False rather than raising when it cannot say yes.
* **No wildcards.** A grant names its data type. There is no term meaning
  "all", so a data type added next year is never covered by an existing row.
* **Expiry is checked at use.** Nothing sweeps expired rows; every check
  compares against the date it is asked about.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

# Scope types. A grant reaches everything below its scope, so `global` covers
# every thing, `group` covers the things in one group (a project or network),
# and `thing` covers exactly one.
SCOPE_GLOBAL = "global"
SCOPE_GROUP = "group"
SCOPE_THING = "thing"
SCOPE_TYPES = frozenset({SCOPE_GLOBAL, SCOPE_GROUP, SCOPE_THING})

# Capabilities.
CAPABILITY_READ = "read"
CAPABILITY_ENTER = "enter"
CAPABILITY_CORRECT = "correct"
CAPABILITY_ADMINISTER = "administer"
CAPABILITIES = frozenset(
    {CAPABILITY_READ, CAPABILITY_ENTER, CAPABILITY_CORRECT, CAPABILITY_ADMINISTER}
)

# Principal types. A destination is not here: publishing to one is recorded as
# consent, not as a grant, which is the two-table half of ADR5.
PRINCIPAL_USER = "user"
PRINCIPAL_ROLE = "role"
# Spelled as the lexicon spells it. The lexicon is the source of truth for
# every controlled term, and a constant that disagreed with it made this
# principal type unwritable: the route validated "api key" against "api_key"
# and rejected every API-key grant with a 422. tests/test_domain_access.py
# pins the two together so it cannot drift again.
PRINCIPAL_API_KEY = "api key"
PRINCIPAL_TYPES = frozenset({PRINCIPAL_USER, PRINCIPAL_ROLE, PRINCIPAL_API_KEY})


class AccessRuleError(ValueError):
    """Base for rule violations. A ValueError, per ADR4."""


class UnknownScopeType(AccessRuleError):
    pass


class UnknownCapability(AccessRuleError):
    pass


class UnknownPrincipalType(AccessRuleError):
    pass


class MissingDataType(AccessRuleError):
    pass


class ScopeIdMismatch(AccessRuleError):
    pass


class BackwardsDateRange(AccessRuleError):
    pass


@dataclass(frozen=True)
class Grant:
    """One row of ``permission_grant``, as plain values."""

    principal_type: str
    principal_id: str
    capability: str
    scope_type: str
    scope_id: int | None
    data_type: str
    starts_at: date
    ends_at: date | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class Consent:
    """One row of ``publication_consent``, as plain values."""

    thing_id: int
    destination_id: int
    data_type: str
    starts_at: date
    ends_at: date | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class AccessRequest:
    """What a caller is asking for.

    ``principals`` is every identity the caller presents at once -- their user
    subject and each role they hold -- because a grant may name any of them.
    ``group_ids`` are the groups the target thing belongs to, which is what
    makes a project-scoped grant reach it.
    """

    capability: str
    data_type: str
    principals: tuple[tuple[str, str], ...] = ()
    thing_id: int | None = None
    group_ids: tuple[int, ...] = field(default_factory=tuple)


def validate_grant(
    principal_type: str,
    capability: str,
    scope_type: str,
    scope_id: int | None,
    data_type: str | None,
    starts_at: date,
    ends_at: date | None,
) -> None:
    """Reject a grant that could not be evaluated honestly.

    Raised before a row is written, so the invariants hold in the table rather
    than in the reader.
    """
    if principal_type not in PRINCIPAL_TYPES:
        raise UnknownPrincipalType(
            f"'{principal_type}' is not a principal type "
            f"({', '.join(sorted(PRINCIPAL_TYPES))})."
        )
    if capability not in CAPABILITIES:
        raise UnknownCapability(
            f"'{capability}' is not a capability ({', '.join(sorted(CAPABILITIES))})."
        )
    if scope_type not in SCOPE_TYPES:
        raise UnknownScopeType(
            f"'{scope_type}' is not a scope type ({', '.join(sorted(SCOPE_TYPES))})."
        )
    if scope_type == SCOPE_GLOBAL and scope_id is not None:
        raise ScopeIdMismatch("A global grant names no scope_id.")
    if scope_type != SCOPE_GLOBAL and scope_id is None:
        raise ScopeIdMismatch(f"A {scope_type}-scoped grant needs a scope_id.")
    if not data_type:
        # The no-wildcard rule. There is deliberately no term meaning "all":
        # a blanket grant is what published data nobody had agreed to publish.
        raise MissingDataType(
            "A grant names its data type. There is no wildcard, so a new data "
            "type is never covered by an existing grant."
        )
    require_forward_range(starts_at, ends_at)


def require_forward_range(starts_at: date, ends_at: date | None) -> None:
    if ends_at is not None and starts_at is not None and ends_at < starts_at:
        raise BackwardsDateRange(
            f"end date {ends_at.isoformat()} precedes start date "
            f"{starts_at.isoformat()}."
        )


def is_active(
    starts_at: date | None,
    ends_at: date | None,
    revoked_at: datetime | None,
    on_date: date,
) -> bool:
    """Whether a row is in force on ``on_date``.

    Revocation wins immediately and is not backdated: a revoked row is dead
    from the moment it is revoked, which is the promise made to a landowner who
    calls to change their mind.
    """
    if revoked_at is not None:
        return False
    if starts_at is not None and on_date < starts_at:
        return False
    if ends_at is not None and on_date > ends_at:
        return False
    return True


def scope_covers(
    scope_type: str,
    scope_id: int | None,
    thing_id: int | None,
    group_ids: tuple[int, ...] = (),
) -> bool:
    """Whether a grant's scope reaches the thing being asked about."""
    if scope_type == SCOPE_GLOBAL:
        return True
    if scope_type == SCOPE_THING:
        return thing_id is not None and scope_id == thing_id
    if scope_type == SCOPE_GROUP:
        return scope_id in set(group_ids)
    # An unrecognized scope type denies rather than raises: a row written by a
    # newer version of the code must not read as permission to an older one.
    return False


def grant_covers(grant: Grant, request: AccessRequest, on_date: date) -> bool:
    """Whether one grant answers one request. Every axis must match."""
    if (grant.principal_type, grant.principal_id) not in request.principals:
        return False
    if grant.capability != request.capability:
        return False
    if grant.data_type != request.data_type:
        return False
    if not is_active(grant.starts_at, grant.ends_at, grant.revoked_at, on_date):
        return False
    return scope_covers(
        grant.scope_type, grant.scope_id, request.thing_id, request.group_ids
    )


def any_grant_allows(grants, request: AccessRequest, on_date: date) -> bool:
    """Default deny: an empty sequence is a no."""
    return any(grant_covers(grant, request, on_date) for grant in grants)


def consent_covers(
    consent: Consent,
    thing_id: int,
    destination_id: int,
    data_type: str,
    on_date: date,
) -> bool:
    """Whether one consent row publishes this data type of this well here."""
    return (
        consent.thing_id == thing_id
        and consent.destination_id == destination_id
        and consent.data_type == data_type
        and is_active(consent.starts_at, consent.ends_at, consent.revoked_at, on_date)
    )


def any_consent_publishes(
    consents,
    thing_id: int,
    destination_id: int,
    data_type: str,
    on_date: date,
) -> bool:
    """Default deny, for the publication half."""
    return any(
        consent_covers(consent, thing_id, destination_id, data_type, on_date)
        for consent in consents
    )


# ============= EOF =============================================
