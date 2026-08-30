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
"""The day-one role baseline (ADR5, 5.2).

An empty grant table denies everyone, including the people who run the system.
These cover the seeder that writes today's access down, and the property that
matters more than convenience: it never gives back what someone took away.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from core.dependencies import admin_function, viewer_function
from db.authorization_audit import AuthorizationAudit
from db.engine import session_ctx
from core.enums import UISurface
from db.permission_grant import PermissionGrant
from main import app
from services.access_seed import (
    ROLE_BASELINE,
    SEED_ACTOR,
    SURFACE_BASELINE,
    planned_entries,
    seed_role_grants,
)
from domain.access import PRINCIPAL_ROLE
from services.visibility import may_see_surface
from tests import client, override_authentication

VIEWER_PAYLOAD = {"sub": "test-viewer", "groups": ["AMP.Viewer"]}


@pytest.fixture(autouse=True)
def seeded_grants():
    app.dependency_overrides[admin_function] = override_authentication(
        default=VIEWER_PAYLOAD
    )
    app.dependency_overrides[viewer_function] = override_authentication(
        default=VIEWER_PAYLOAD
    )

    yield

    app.dependency_overrides = {}
    with session_ctx() as session:
        session.execute(
            delete(PermissionGrant).where(PermissionGrant.granted_by == SEED_ACTOR)
        )
        session.execute(
            delete(AuthorizationAudit).where(AuthorizationAudit.actor == SEED_ACTOR)
        )
        session.commit()


def seeded_rows(session):
    return (
        session.execute(
            select(PermissionGrant).where(PermissionGrant.granted_by == SEED_ACTOR)
        )
        .scalars()
        .all()
    )


# ------ the seeder ----------


def test_seeding_writes_one_row_per_role_capability_and_data_type():
    with session_ctx() as session:
        plan = seed_role_grants(session)
        assert len(plan.created) == len(planned_entries())
        assert len(seeded_rows(session)) == len(planned_entries())


def test_seeding_twice_creates_nothing_the_second_time():
    with session_ctx() as session:
        seed_role_grants(session)
        again = seed_role_grants(session)

    assert again.created == []
    assert len(again.skipped) == len(planned_entries())


def test_a_preview_writes_nothing():
    with session_ctx() as session:
        plan = seed_role_grants(session, apply=False)
        assert plan.created
        assert seeded_rows(session) == []


def test_a_revoked_baseline_grant_is_not_resurrected():
    """Narrowing the baseline is the point; re-running must not undo it."""
    with session_ctx() as session:
        seed_role_grants(session)
        grant = (
            session.execute(
                select(PermissionGrant).where(
                    PermissionGrant.granted_by == SEED_ACTOR,
                    PermissionGrant.principal_id == "AMP.Viewer",
                    PermissionGrant.data_type == "water chemistry",
                )
            )
            .scalars()
            .one()
        )
        grant.revoked_at = datetime.now(timezone.utc)
        grant.revoked_by = "someone-who-decided"
        session.commit()

        plan = seed_role_grants(session)

    assert plan.created == []


def test_every_seeded_grant_is_marked_as_history_not_judgement():
    with session_ctx() as session:
        seed_role_grants(session)
        rows = seeded_rows(session)

    assert all(row.granted_by == SEED_ACTOR for row in rows)
    assert all("ADR5" in row.reason for row in rows)
    assert all(row.scope_type == "global" and row.scope_id is None for row in rows)


def test_seeding_is_audited():
    with session_ctx() as session:
        seed_role_grants(session)
        events = (
            session.execute(
                select(AuthorizationAudit).where(AuthorizationAudit.actor == SEED_ACTOR)
            )
            .scalars()
            .all()
        )

    assert len(events) == len(planned_entries())
    assert {event.event_type for event in events} == {"grant.created"}


def test_a_viewer_gets_read_and_nothing_else():
    """The tiers nest within a family; the baseline has to say so."""
    assert ROLE_BASELINE["AMP.Viewer"] == ("read",)
    assert set(ROLE_BASELINE["AMP.Admin"]) > set(ROLE_BASELINE["AMP.Editor"])
    assert set(ROLE_BASELINE["AMP.Editor"]) > set(ROLE_BASELINE["AMP.Viewer"])


def test_the_dark_workbench_group_is_not_seeded():
    """AMP.Staging gates a workbench still being validated. Seeding it would
    grant exactly the access nobody intended."""
    assert "AMP.Staging" not in ROLE_BASELINE
    assert not any(role.startswith("Lexicon") for role in ROLE_BASELINE)


# ------ what it is for ----------


def test_decision_says_no_before_seeding():
    response = client.get(
        "/access/decision", params={"capability": "read", "data_type": "water level"}
    )
    assert response.json()["allowed"] is False


def test_decision_says_yes_to_a_role_holder_after_seeding():
    with session_ctx() as session:
        seed_role_grants(session)

    allowed = client.get(
        "/access/decision", params={"capability": "read", "data_type": "water level"}
    ).json()
    assert allowed["allowed"] is True
    assert "role:AMP.Viewer" in allowed["principals"]


def test_a_viewer_still_cannot_correct_after_seeding():
    with session_ctx() as session:
        seed_role_grants(session)

    response = client.get(
        "/access/decision",
        params={"capability": "correct", "data_type": "water level"},
    )
    assert response.json()["allowed"] is False


def test_the_baseline_is_global_so_it_reaches_any_thing():
    with session_ctx() as session:
        seed_role_grants(session)

    response = client.get(
        "/access/decision",
        params={
            "capability": "read",
            "data_type": "water level",
            "thing_id": 999999,
        },
    )
    assert response.json()["allowed"] is True


def test_seeded_grants_start_today_not_retroactively():
    with session_ctx() as session:
        seed_role_grants(session)
        rows = seeded_rows(session)

    assert all(row.starts_at == date.today() for row in rows)


# ------ the screen half ----------


def test_a_seeded_surface_grant_is_global_view_over_no_data_type():
    """The only shape a surface grant has; anything else could never match."""
    with session_ctx() as session:
        seed_role_grants(session)
        rows = [row for row in seeded_rows(session) if row.ui_surface]

    assert rows
    assert all(row.capability == "view" for row in rows)
    assert all(row.data_type is None for row in rows)
    assert all(row.scope_type == "global" and row.scope_id is None for row in rows)


def test_every_seeded_surface_is_a_real_term():
    """A typo here would be a foreign key error mid-seed, in production."""
    known = {member.value for member in UISurface}
    seeded = {surface for surfaces in SURFACE_BASELINE.values() for surface in surfaces}
    assert seeded <= known


def test_the_dark_workbench_screen_is_not_seeded():
    """Same reason AMP.Staging holds no data grants: it ships dark."""
    seeded = {surface for surfaces in SURFACE_BASELINE.values() for surface in surfaces}
    assert "ocotillo.hydrograph-correction" not in seeded


def test_only_admin_gets_the_access_console():
    holders = {
        role
        for role, surfaces in SURFACE_BASELINE.items()
        if "ocotillo.access-grants" in surfaces
    }
    assert holders == {"AMP.Admin"}


def test_the_lexicon_screen_follows_the_lexicon_family():
    """Vocabulary is not data: the lexicon group gets the screen and no
    data grants, and the top of the data ladder does not inherit it."""
    assert SURFACE_BASELINE["Lexicon.Editor"] == ("ocotillo.lexicon",)
    assert "ocotillo.lexicon" not in SURFACE_BASELINE["AMP.Admin"]
    assert "Lexicon.Editor" not in ROLE_BASELINE


def test_a_seeded_surface_grant_opens_the_screen():
    with session_ctx() as session:
        seed_role_grants(session)
        allowed = may_see_surface(
            session,
            principals=((PRINCIPAL_ROLE, "AMP.Viewer"),),
            ui_surface="ocotillo.map",
        )
        denied = may_see_surface(
            session,
            principals=((PRINCIPAL_ROLE, "AMP.Viewer"),),
            ui_surface="ocotillo.access-grants",
        )

    assert allowed is True
    assert denied is False
