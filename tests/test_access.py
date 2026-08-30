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

ADMIN_PAYLOAD = {"sub": "test-admin", "groups": ["AMP.Admin"]}
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
def public_destination():
    response = client.post(
        "/access/destination",
        json={
            "slug": "test-public-web",
            "name": "Test Public Web",
            "destination_kind": "public web",
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
    assert len(entries) == 1
    assert entries[0]["thing_id"] == water_well_thing.id
    assert entries[0]["data_types"] == ["water level"]
    assert entries[0]["properties"]["name"] == water_well_thing.name

    assert published(data_type="water chemistry") == []


# ------ field projection ----------


def test_a_destination_receives_only_its_allowlisted_fields(
    destination, water_well_thing
):
    consent_to(water_well_thing.id, "water level")
    properties = published()[0]["properties"]

    # Named for the harvester audience in core/field-allowlists.yml.
    assert set(properties) == {
        "id",
        "name",
        "thing_type",
        "well_depth",
        "hole_depth",
        "well_casing_depth",
        "well_completion_date",
    }


def test_never_public_fields_reach_nobody(destination, water_well_thing):
    consent_to(water_well_thing.id, "water level")
    entry = published()[0]

    for column in ("created_by_id", "created_by_name", "nma_pk_welldata"):
        assert column not in entry["properties"]
    for column in ("nma_location_notes", "nma_coordinate_notes"):
        assert column not in entry["location"]


def test_coordinates_are_rounded_for_the_audience(
    destination, public_destination, water_well_thing
):
    """The same well, two audiences, two precisions -- not published or hidden."""
    consent_to(water_well_thing.id, "water level")
    client.post(
        "/access/consent",
        json={
            "thing_id": water_well_thing.id,
            "destination_slug": public_destination["slug"],
            "data_type": "water level",
            "starts_at": TODAY.isoformat(),
        },
    )

    harvester_location = published()[0]["location"]
    public_response = client.get(
        f"/access/destination/{public_destination['slug']}/thing"
    )
    public_location = public_response.json()[0]["location"]

    assert harvester_location["latitude"] == round(harvester_location["latitude"], 4)
    assert public_location["latitude"] == round(public_location["latitude"], 2)
    assert public_location["latitude"] != harvester_location["latitude"]
    # Rounded, not withheld: the well still appears on the public map.
    assert public_location["latitude"] is not None


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
    # A screen is opened with `view`; the data verbs belong to a data_type
    # grant, and the route refuses the crossing.
    if overrides.get("ui_surface") and "capability" not in overrides:
        payload["capability"] = "view"
    payload.update(overrides)
    response = client.post("/access/grant", json=payload)
    if response.status_code == 201:
        grants.append(response.json()["id"])
    return response


def listed_grants(**params):
    """Ids on one page of the grant listing.

    `size` is generous because the seeded baseline shares this database and a
    default page would push a freshly written grant off the end.
    """
    params.setdefault("size", 200)
    response = client.get("/access/grant", params=params)
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


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
    """No wildcards. A grant naming neither subject is rejected by the rule in
    domain/access.py, which the route surfaces as a 422."""
    assert make_grant(grants, data_type=None).status_code == 422


def test_listing_grants_with_no_filter_returns_everything(grants):
    grant_id = make_grant(grants).json()["id"]

    assert grant_id in listed_grants()


def test_listing_grants_filters_by_data_type(grants):
    grant_id = make_grant(grants).json()["id"]

    assert grant_id in listed_grants(data_type="water level")
    assert grant_id not in listed_grants(data_type="water chemistry")


def test_listing_grants_hides_revoked_ones_by_default(grants):
    grant_id = make_grant(grants).json()["id"]
    client.post(f"/access/grant/{grant_id}/revocation")

    assert listed_grants(principal_id=ADMIN_PAYLOAD["sub"]) == []
    assert listed_grants(principal_id=ADMIN_PAYLOAD["sub"], include_revoked=True) == [
        grant_id
    ]


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


# ------ UI-surface grants ----------
#
# A grant can open a screen instead of reaching data. These go through the
# route so the XOR, the global-only rule, and the decision endpoint are all
# exercised the way the admin console will use them.


def test_a_surface_grant_opens_that_screen(grants):
    assert (
        make_grant(grants, data_type=None, ui_surface="ocotillo.lexicon").status_code
        == 201
    )

    assert decision(capability="view", ui_surface="ocotillo.lexicon")["allowed"] is True


def test_a_surface_grant_opens_only_that_screen(grants):
    make_grant(grants, data_type=None, ui_surface="ocotillo.lexicon")

    assert (
        decision(capability="view", ui_surface="ocotillo.location")["allowed"] is False
    )


def test_a_data_grant_does_not_open_a_screen(grants):
    make_grant(grants)

    assert (
        decision(capability="view", ui_surface="ocotillo.lexicon")["allowed"] is False
    )


def test_a_surface_grant_does_not_reach_data(grants):
    make_grant(grants, data_type=None, ui_surface="ocotillo.lexicon")

    assert decision(capability="read", data_type="water level")["allowed"] is False


def test_a_grant_naming_both_subjects_is_rejected(grants):
    response = make_grant(grants, ui_surface="ocotillo.lexicon")

    assert response.status_code == 422
    assert "not both" in response.text


def test_a_scoped_surface_grant_is_rejected(grants, water_well_thing):
    """It could never match: the UI never asks about a screen for one thing."""
    response = make_grant(
        grants,
        data_type=None,
        ui_surface="ocotillo.lexicon",
        scope_type="thing",
        scope_id=water_well_thing.id,
    )

    assert response.status_code == 422
    assert "always global" in response.text


def test_revoking_a_surface_grant_closes_the_screen(grants):
    grant_id = make_grant(grants, data_type=None, ui_surface="ocotillo.lexicon").json()[
        "id"
    ]
    assert decision(capability="view", ui_surface="ocotillo.lexicon")["allowed"] is True

    assert client.post(f"/access/grant/{grant_id}/revocation").status_code == 201

    assert (
        decision(capability="view", ui_surface="ocotillo.lexicon")["allowed"] is False
    )


def test_asking_about_both_subjects_at_once_is_rejected(grants):
    """Two questions, two answers. The route refuses rather than picking one."""
    response = client.get(
        "/access/decision",
        params={
            "capability": "read",
            "data_type": "water level",
            "ui_surface": "ocotillo.lexicon",
        },
    )

    assert response.status_code == 422


def test_asking_about_neither_subject_is_a_no(grants):
    """A question the layer cannot answer is not a yes."""
    assert decision(capability="read")["allowed"] is False


def test_listing_grants_filters_by_ui_surface(grants):
    surface_id = make_grant(
        grants, data_type=None, ui_surface="ocotillo.lexicon"
    ).json()["id"]
    data_id = make_grant(grants).json()["id"]

    ids = listed_grants(ui_surface="ocotillo.lexicon")

    assert surface_id in ids
    assert data_id not in ids


def test_a_surface_grant_is_logged_like_any_other(grants):
    make_grant(grants, data_type=None, ui_surface="ocotillo.lexicon")

    with session_ctx() as session:
        logged = (
            session.execute(
                select(AuthorizationAudit).where(
                    AuthorizationAudit.actor == ADMIN_PAYLOAD["sub"]
                )
            )
            .scalars()
            .all()
        )

    assert any(entry.detail.get("ui_surface") == "ocotillo.lexicon" for entry in logged)


# ============= EOF =============================================


def test_the_grant_listing_is_paged(grants):
    """The admin-wide view is not small: the day-one baseline alone is dozens
    of rows before anybody grants anything by hand."""
    for _ in range(3):
        make_grant(grants)

    page = client.get("/access/grant", params={"size": 2, "page": 1})
    body = page.json()

    assert page.status_code == 200
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["size"] == 2

    second = client.get("/access/grant", params={"size": 2, "page": 2}).json()
    assert not set(row["id"] for row in body["items"]) & set(
        row["id"] for row in second["items"]
    )


def test_paging_is_stable_across_pages(grants):
    """Ordered by id, so a row cannot appear on two pages or on none."""
    for _ in range(5):
        make_grant(grants)

    everything = listed_grants(size=500)
    walked = []
    for page_number in (1, 2, 3):
        walked.extend(
            row["id"]
            for row in client.get(
                "/access/grant", params={"size": 2, "page": page_number}
            ).json()["items"]
        )

    assert walked == everything[: len(walked)]
    assert len(walked) == len(set(walked))
