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
"""The ADR5 visibility layer, end to end through its first tenant.

These exercise the promise the model is for: an owner who shares water levels
but not chemistry, and a withdrawal that takes effect on the next read.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import delete, select

from core.dependencies import admin_function, viewer_function
from main import app
from db.authorization_audit import AuthorizationAudit
from db.destination import Destination
from db.engine import session_ctx
from db.permission_grant import PermissionGrant
from db.publication_consent import PublicationConsent
from tests import client, override_authentication

ADMIN_PAYLOAD = {"sub": "test-admin", "groups": ["Admin"]}
SLUG = "test-harvester"
TODAY = date.today()


@pytest.fixture(autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[admin_function] = override_authentication(
        default=ADMIN_PAYLOAD
    )
    app.dependency_overrides[viewer_function] = override_authentication(
        default=ADMIN_PAYLOAD
    )

    yield

    app.dependency_overrides = {}


@pytest.fixture
def destination():
    response = client.post(
        "/access/destination",
        json={
            "slug": SLUG,
            "name": "Test Harvester",
            "destination_kind": "harvester",
            "description": "Stands in for NGWMN.",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()

    yield created

    with session_ctx() as session:
        session.execute(
            delete(PublicationConsent).where(
                PublicationConsent.destination_id == created["id"]
            )
        )
        session.execute(delete(Destination).where(Destination.id == created["id"]))
        session.execute(
            delete(AuthorizationAudit).where(
                AuthorizationAudit.actor == ADMIN_PAYLOAD["sub"]
            )
        )
        session.commit()


@pytest.fixture
def grants():
    created = []

    yield created

    with session_ctx() as session:
        for grant_id in created:
            session.execute(
                delete(PermissionGrant).where(PermissionGrant.id == grant_id)
            )
        session.execute(
            delete(AuthorizationAudit).where(
                AuthorizationAudit.actor == ADMIN_PAYLOAD["sub"]
            )
        )
        session.commit()


def consent_to(thing_id, data_type, **overrides):
    payload = {
        "thing_id": thing_id,
        "destination_slug": SLUG,
        "data_type": data_type,
        "starts_at": TODAY.isoformat(),
    }
    payload.update(overrides)
    return client.post("/access/consent", json=payload)


def published(**params):
    response = client.get(f"/access/destination/{SLUG}/thing", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ------ destinations ----------


def test_register_a_destination(destination):
    assert destination["slug"] == SLUG
    assert destination["active"] is True


def test_a_duplicate_slug_is_a_conflict(destination):
    response = client.post(
        "/access/destination",
        json={"slug": SLUG, "name": "Again", "destination_kind": "harvester"},
    )
    assert response.status_code == 409


def test_an_unknown_destination_is_a_404():
    response = client.get("/access/destination/nobody-registered-this/thing")
    assert response.status_code == 404


# ------ the case the model exists for ----------


def test_levels_yes_chemistry_no(destination, water_well_thing):
    """The kitchen-table promise: per data type, on one well."""
    assert consent_to(water_well_thing.id, "water level").status_code == 201

    entries = published()
    assert entries == [
        {
            "thing_id": water_well_thing.id,
            "name": water_well_thing.name,
            "data_types": ["water level"],
        }
    ]
    assert published(data_type="water chemistry") == []


def test_nothing_is_published_without_consent(destination, water_well_thing):
    """Default deny. A registered destination starts with nothing."""
    assert published() == []


def test_withdrawal_takes_effect_on_the_next_read(destination, water_well_thing):
    consent_id = consent_to(water_well_thing.id, "water level").json()["id"]
    assert len(published()) == 1

    revocation = client.post(f"/access/consent/{consent_id}/revocation")
    assert revocation.status_code == 201
    assert revocation.json()["revoked_by"] == ADMIN_PAYLOAD["sub"]

    assert published() == []


def test_consent_cannot_be_withdrawn_twice(destination, water_well_thing):
    consent_id = consent_to(water_well_thing.id, "water level").json()["id"]
    client.post(f"/access/consent/{consent_id}/revocation")

    assert client.post(f"/access/consent/{consent_id}/revocation").status_code == 422


def test_withdrawn_consent_is_kept_for_the_record(destination, water_well_thing):
    consent_id = consent_to(water_well_thing.id, "water level").json()["id"]
    client.post(f"/access/consent/{consent_id}/revocation")

    live = client.get("/access/consent", params={"thing_id": water_well_thing.id})
    assert live.json() == []

    history = client.get(
        "/access/consent",
        params={"thing_id": water_well_thing.id, "include_revoked": True},
    )
    assert [row["id"] for row in history.json()] == [consent_id]


def test_expired_consent_stops_publishing(destination, water_well_thing):
    yesterday = TODAY - timedelta(days=1)
    consent_to(
        water_well_thing.id,
        "water level",
        starts_at=(TODAY - timedelta(days=30)).isoformat(),
        ends_at=yesterday.isoformat(),
    )

    assert published() == []
    assert len(published(on_date=yesterday.isoformat())) == 1


def test_consent_to_an_unknown_destination_is_a_404(water_well_thing):
    response = client.post(
        "/access/consent",
        json={
            "thing_id": water_well_thing.id,
            "destination_slug": "not-registered",
            "data_type": "water level",
            "starts_at": TODAY.isoformat(),
        },
    )
    assert response.status_code == 404


# ------ grants ----------


def make_grant(grants, **overrides):
    payload = {
        "principal_type": "user",
        "principal_id": ADMIN_PAYLOAD["sub"],
        "capability": "read",
        "scope_type": "global",
        "scope_id": None,
        "data_type": "water level",
        "starts_at": TODAY.isoformat(),
        "reason": "test",
    }
    payload.update(overrides)
    response = client.post("/access/grant", json=payload)
    if response.status_code == 201:
        grants.append(response.json()["id"])
    return response


def decision(**params):
    response = client.get("/access/decision", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_grant_answers_only_for_its_data_type(grants):
    assert make_grant(grants).status_code == 201

    assert decision(capability="read", data_type="water level")["allowed"] is True
    assert decision(capability="read", data_type="water chemistry")["allowed"] is False


def test_no_grant_is_a_no(grants):
    assert decision(capability="read", data_type="water level")["allowed"] is False


def test_a_grant_answers_only_for_its_capability(grants):
    make_grant(grants)

    assert decision(capability="correct", data_type="water level")["allowed"] is False


def test_revoking_a_grant_is_effective_immediately(grants):
    grant_id = make_grant(grants).json()["id"]
    assert decision(capability="read", data_type="water level")["allowed"] is True

    assert client.post(f"/access/grant/{grant_id}/revocation").status_code == 201

    assert decision(capability="read", data_type="water level")["allowed"] is False


def test_a_thing_scoped_grant_stops_at_that_thing(grants, water_well_thing):
    make_grant(grants, scope_type="thing", scope_id=water_well_thing.id)

    covered = decision(
        capability="read", data_type="water level", thing_id=water_well_thing.id
    )
    other = decision(
        capability="read", data_type="water level", thing_id=water_well_thing.id + 9999
    )
    assert covered["allowed"] is True
    assert other["allowed"] is False


def test_a_global_grant_with_a_scope_id_is_rejected(grants):
    """The rule lives in domain/access.py; the route surfaces it as a 422."""
    assert make_grant(grants, scope_id=7).status_code == 422


def test_a_grant_naming_no_data_type_cannot_be_written(grants):
    """No wildcards. Pydantic rejects it before the service is reached."""
    assert make_grant(grants, data_type=None).status_code == 422


def test_listing_grants_hides_revoked_ones_by_default(grants):
    grant_id = make_grant(grants).json()["id"]
    client.post(f"/access/grant/{grant_id}/revocation")

    live = client.get("/access/grant", params={"principal_id": ADMIN_PAYLOAD["sub"]})
    assert live.json() == []

    history = client.get(
        "/access/grant",
        params={"principal_id": ADMIN_PAYLOAD["sub"], "include_revoked": True},
    )
    assert [row["id"] for row in history.json()] == [grant_id]


# ------ audit ----------


def audit_events():
    with session_ctx() as session:
        return [
            row.event_type
            for row in session.execute(
                select(AuthorizationAudit)
                .where(AuthorizationAudit.actor == ADMIN_PAYLOAD["sub"])
                .order_by(AuthorizationAudit.id)
            ).scalars()
        ]


def test_every_authorization_change_is_logged(destination, grants, water_well_thing):
    consent_id = consent_to(water_well_thing.id, "water level").json()["id"]
    client.post(f"/access/consent/{consent_id}/revocation")
    grant_id = make_grant(grants).json()["id"]
    client.post(f"/access/grant/{grant_id}/revocation")

    assert audit_events() == [
        "destination.registered",
        "consent.recorded",
        "consent.revoked",
        "grant.created",
        "grant.revoked",
    ]


def test_the_log_records_who_and_what(destination, water_well_thing):
    consent_to(water_well_thing.id, "water level")

    with session_ctx() as session:
        entry = (
            session.execute(
                select(AuthorizationAudit)
                .where(AuthorizationAudit.event_type == "consent.recorded")
                .order_by(AuthorizationAudit.id.desc())
            )
            .scalars()
            .first()
        )

    assert entry.actor == ADMIN_PAYLOAD["sub"]
    assert entry.subject_table == "publication_consent"
    assert entry.detail["thing_id"] == water_well_thing.id
    assert entry.detail["data_type"] == "water level"
