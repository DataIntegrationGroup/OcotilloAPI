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
services/access_seed.py

The day-one baseline from ADR5, 5.2: existing Authentik roles become role
principals holding broad grants, so nobody's access changes on the day the
grant table starts being consulted.

Without this the grant table is empty, and an empty grant table means default
deny -- correct, and useless: ``/access/decision`` says no to everyone,
including the people who administer the system.

Three properties this seeder has to have:

* **Idempotent.** Running it twice creates nothing the second time.
* **Not a resurrection.** A seeded grant somebody revoked stays revoked. The
  skip check looks at every seeded row, not only the live ones, so re-running
  after a deliberate revocation does not quietly undo it.
* **Marked.** Every row it writes carries ``granted_by`` set to the seed actor
  and a reason naming the ADR, so a grant that exists because of institutional
  history is distinguishable from one somebody decided on.

The mapping mirrors the role families in ``core/dependencies.py``. It is a
starting point, not a statement about what each role should have: narrowing it
is the point of the whole exercise, and every narrowing is a revocation
somebody makes deliberately.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select

from core.enums import AccessDataType
from db.permission_grant import PermissionGrant
from domain.access import (
    CAPABILITY_ADMINISTER,
    CAPABILITY_CORRECT,
    CAPABILITY_ENTER,
    CAPABILITY_READ,
    PRINCIPAL_ROLE,
    SCOPE_GLOBAL,
)
from services.access_admin import create_grant

# Recorded as the granting actor. Not a person, and deliberately obvious in
# the audit log: these grants exist because of what access already was, not
# because someone weighed them.
SEED_ACTOR = "system:day-one-baseline"
SEED_REASON = (
    "Day-one baseline (ADR5, 5.2): preserves the access this Authentik role "
    "already had before grants were consulted. Narrow it deliberately."
)

READ_ONLY = (CAPABILITY_READ,)
EDIT = (CAPABILITY_READ, CAPABILITY_ENTER, CAPABILITY_CORRECT)
FULL = EDIT + (CAPABILITY_ADMINISTER,)

# Authentik group -> capabilities, mirroring core/dependencies.py. The tiers
# nest within a family, so an Admin's row set is a superset of an Editor's.
#
# Lexicon* is absent: it gates vocabulary, not data. AMP.Staging is absent
# because it gates a workbench that ships dark, and seeding it would be the
# one thing nobody intended -- granting access to something still being
# validated.
ROLE_BASELINE = {
    "Viewer": READ_ONLY,
    "Editor": EDIT,
    "Admin": FULL,
    "AMPViewer": READ_ONLY,
    "AMPEditor": EDIT,
    "AMPAdmin": FULL,
    # The desktop-GIS mount reads; it has never written.
    "OGCInternal": READ_ONLY,
}


@dataclass
class SeedPlan:
    """What seeding would do, or did."""

    created: list = field(default_factory=list)
    skipped: list = field(default_factory=list)

    def describe(self, entry) -> str:
        role, capability, data_type = entry
        return f"role:{role} may {capability} {data_type} (global)"


def data_types() -> tuple:
    """Every access data type there is, named one by one.

    No wildcard: this is a list of rows, so a data type added later is not
    covered until somebody seeds or grants it.
    """
    return tuple(member.value for member in AccessDataType)


def planned_entries() -> list:
    return [
        (role, capability, data_type)
        for role, capabilities in ROLE_BASELINE.items()
        for capability in capabilities
        for data_type in data_types()
    ]


def _already_seeded(session) -> set:
    """Every (role, capability, data type) this seeder has ever written.

    Revoked rows count. A grant somebody took away is not re-created by
    running the seeder again.
    """
    rows = session.execute(
        select(
            PermissionGrant.principal_id,
            PermissionGrant.capability,
            PermissionGrant.data_type,
        ).where(
            PermissionGrant.principal_type == PRINCIPAL_ROLE,
            PermissionGrant.granted_by == SEED_ACTOR,
        )
    ).all()
    return {(role, capability, data_type) for role, capability, data_type in rows}


def seed_role_grants(session, starts_at: date = None, apply: bool = True) -> SeedPlan:
    """Create the missing baseline grants. Safe to run repeatedly.

    With ``apply=False`` nothing is written and the plan describes what would
    be. Grants are security state, so the CLI previews by default.
    """
    starts_at = starts_at or date.today()
    seeded = _already_seeded(session)

    plan = SeedPlan()
    for entry in planned_entries():
        if entry in seeded:
            plan.skipped.append(entry)
            continue

        plan.created.append(entry)
        if not apply:
            continue

        role, capability, data_type = entry
        create_grant(
            session,
            SEED_ACTOR,
            principal_type=PRINCIPAL_ROLE,
            principal_id=role,
            capability=capability,
            scope_type=SCOPE_GLOBAL,
            scope_id=None,
            data_type=data_type,
            starts_at=starts_at,
            ends_at=None,
            reason=SEED_REASON,
        )

    return plan


# ============= EOF =============================================
