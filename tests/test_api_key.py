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
"""Tests for personal API keys.

Two layers:

* the rules in domain/api_key.py, which need nothing but values,
* the routes and the resolver, which need a session.

The middleware gate itself (core/internal_ogc_auth.py) is not exercised through
the client here: CI runs with AUTHENTIK_DISABLE_AUTHENTICATION=1, which makes
the middleware pass every request through before it looks at a credential. The
resolver it delegates to is tested directly instead.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from core.dependencies import internal_ogc_function
from db.api_key import ApiKey
from db.engine import session_ctx
from domain import api_key as rules
from main import app
from services.api_key_auth import resolve_api_key
from tests import client, override_authentication

OWNER = {"name": "Key Holder", "sub": "owner-sub-apikey-test"}
OTHER_OWNER_SUB = "someone-else-apikey-test"


@pytest.fixture(autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[internal_ogc_function] = override_authentication(
        default=OWNER
    )
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def clean_keys():
    """Remove every key either test identity owns, before and after."""

    def _purge():
        with session_ctx() as session:
            for row in session.scalars(
                select(ApiKey).where(
                    ApiKey.owner_sub.in_([OWNER["sub"], OTHER_OWNER_SUB])
                )
            ).all():
                session.delete(row)
            session.commit()

    _purge()
    yield
    _purge()


def _create(name="Field laptop", **payload) -> dict:
    resp = client.post("/api_key", json={"name": name, **payload})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _insert_key(session, *, token=None, owner_sub=OWNER["sub"], **overrides) -> ApiKey:
    """A key written straight to the table, for states the API will not create."""
    token = token or rules.generate_token()
    now = datetime.now(timezone.utc)
    key = ApiKey(
        token_digest=rules.digest_token(token),
        token_preview=rules.preview_token(token),
        name=overrides.pop("name", "Direct insert"),
        owner_sub=owner_sub,
        owner_name=overrides.pop("owner_name", "Key Holder"),
        scope=rules.SCOPE_OGC_INTERNAL,
        expires_at=overrides.pop("expires_at", rules.expiry_for(now)),
        **overrides,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return key


# DOMAIN RULES =================================================================


def test_generated_token_is_prefixed_and_recognizable():
    token = rules.generate_token()
    assert token.startswith("ocot_")
    assert rules.looks_like_api_key(token)
    # A JWT must not be mistaken for one, or every bearer request pays for a
    # database lookup that can only miss.
    assert not rules.looks_like_api_key("eyJhbGciOiJSUzI1NiJ9.payload.signature")


def test_generated_tokens_are_distinct():
    assert len({rules.generate_token() for _ in range(100)}) == 100


def test_digest_is_sha256_hex():
    digest = rules.digest_token("ocot_example")
    assert len(digest) == 64
    int(digest, 16)  # raises if it is not hex
    assert rules.digests_equal(digest, rules.digest_token("ocot_example"))
    assert not rules.digests_equal(digest, rules.digest_token("ocot_other"))


def test_preview_hides_the_body_of_the_token():
    token = rules.generate_token()
    preview = rules.preview_token(token)
    assert preview.startswith(token[:10])
    assert preview.endswith(token[-4:])
    # The middle -- the part that makes the token a secret -- is gone.
    assert token[12:-6] not in preview
    assert len(preview) < len(token)


def test_default_expiry_is_365_days():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    assert rules.expiry_for(now) == now + timedelta(days=365)


def test_a_shorter_lifetime_is_honored_and_a_longer_one_is_clamped():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    assert rules.expiry_for(now, timedelta(days=7)) == now + timedelta(days=7)
    assert rules.expiry_for(now, timedelta(days=9999)) == now + rules.MAX_LIFETIME


def test_a_non_positive_lifetime_is_rejected():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    with pytest.raises(rules.ApiKeyError):
        rules.expiry_for(now, timedelta(0))


def test_a_missing_expiry_reads_as_expired():
    # The column is NOT NULL, so NULL means a row written around the create
    # path. A credential of unknown provenance has to fail closed.
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    assert rules.is_expired(None, now)
    assert not rules.is_usable(None, None, now)


def test_usability_covers_revocation_and_expiry():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    later = now + timedelta(days=1)
    earlier = now - timedelta(days=1)
    assert rules.is_usable(None, later, now)
    assert not rules.is_usable(now, later, now)  # revoked
    assert not rules.is_usable(None, earlier, now)  # expired
    assert not rules.is_usable(None, now, now)  # expires exactly now


def test_last_used_is_written_at_most_once_per_resolution():
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    assert rules.should_touch_last_used(None, now)
    assert rules.should_touch_last_used(now - rules.LAST_USED_RESOLUTION, now)
    assert not rules.should_touch_last_used(now - timedelta(seconds=30), now)


def test_blank_names_fall_back_and_long_names_are_rejected():
    assert rules.normalize_name("   ") == rules.DEFAULT_NAME
    assert rules.normalize_name(None) == rules.DEFAULT_NAME
    assert rules.normalize_name("  Field laptop  ") == "Field laptop"
    with pytest.raises(rules.ApiKeyError):
        rules.normalize_name("x" * (rules.MAX_NAME_LENGTH + 1))


# POST =========================================================================


def test_create_returns_the_token_exactly_once():
    created = _create()
    token = created["token"]
    assert token.startswith("ocot_")
    assert created["token_preview"] == rules.preview_token(token)

    # Every later read of the same key is token-free.
    listed = client.get("/api_key").json()
    assert [key["id"] for key in listed] == [created["id"]]
    assert "token" not in listed[0]


def test_create_stores_only_the_digest():
    created = _create()
    token = created["token"]

    with session_ctx() as session:
        row = session.get(ApiKey, created["id"])
        assert row.token_digest == rules.digest_token(token)
        # No column anywhere on the row holds the token itself.
        stored = [value for value in row.__dict__.values() if isinstance(value, str)]
        assert token not in stored


def test_create_defaults_to_a_365_day_expiry():
    created = _create()
    expires_at = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
    created_at = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    assert abs((expires_at - created_at) - timedelta(days=365)) < timedelta(minutes=1)


def test_create_honors_a_shorter_lifetime():
    created = _create(lifetime_days=30)
    expires_at = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
    created_at = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    assert abs((expires_at - created_at) - timedelta(days=30)) < timedelta(minutes=1)


def test_create_clamps_a_longer_lifetime_rather_than_rejecting_it():
    created = _create(lifetime_days=3650)
    expires_at = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
    created_at = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00"))
    assert abs((expires_at - created_at) - rules.MAX_LIFETIME) < timedelta(minutes=1)


def test_create_rejects_a_non_positive_lifetime():
    assert (
        client.post("/api_key", json={"name": "x", "lifetime_days": 0}).status_code
        == 422
    )


def test_create_records_the_owner_and_the_scope():
    created = _create()
    assert created["scope"] == rules.SCOPE_OGC_INTERNAL
    with session_ctx() as session:
        row = session.get(ApiKey, created["id"])
        assert row.owner_sub == OWNER["sub"]
        assert row.owner_name == OWNER["name"]
        assert row.created_by_id == OWNER["sub"]


# GET ==========================================================================


def test_list_shows_active_keys_first_then_newest_first():
    with session_ctx() as session:
        now = datetime.now(timezone.utc)
        revoked = _insert_key(session, name="revoked", revoked_at=now)
        older = _insert_key(session, name="older")
        older.created_at = now - timedelta(days=2)
        newer = _insert_key(session, name="newer")
        newer.created_at = now - timedelta(days=1)
        session.commit()
        expected = [newer.id, older.id, revoked.id]

    assert [key["id"] for key in client.get("/api_key").json()] == expected


def test_list_never_shows_another_users_keys():
    mine = _create()
    with session_ctx() as session:
        theirs = _insert_key(session, owner_sub=OTHER_OWNER_SUB, name="not yours")
        theirs_id = theirs.id

    listed = client.get("/api_key").json()
    assert [key["id"] for key in listed] == [mine["id"]]
    assert theirs_id not in [key["id"] for key in listed]


# PATCH ========================================================================


def test_rename_changes_only_the_name():
    created = _create(name="Old name")
    resp = client.patch(f"/api_key/{created['id']}", json={"name": "  New name  "})
    assert resp.status_code == 200, resp.text
    renamed = resp.json()
    assert renamed["name"] == "New name"
    assert renamed["token_preview"] == created["token_preview"]
    assert renamed["expires_at"] == created["expires_at"]
    assert "token" not in renamed


def test_rename_is_allowed_on_a_revoked_key():
    # Annotating a key you have already revoked ("laptop, stolen") is useful,
    # and the label is not a credential.
    created = _create()
    assert client.delete(f"/api_key/{created['id']}").status_code == 204
    resp = client.patch(f"/api_key/{created['id']}", json={"name": "laptop, stolen"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "laptop, stolen"


def test_rename_of_another_users_key_is_a_404():
    with session_ctx() as session:
        theirs = _insert_key(session, owner_sub=OTHER_OWNER_SUB)
        theirs_id = theirs.id

    resp = client.patch(f"/api_key/{theirs_id}", json={"name": "mine now"})
    assert resp.status_code == 404

    with session_ctx() as session:
        assert session.get(ApiKey, theirs_id).name == "Direct insert"


def test_rename_of_a_missing_key_is_a_404():
    assert client.patch("/api_key/9999999", json={"name": "x"}).status_code == 404


# DELETE =======================================================================


def test_revoke_keeps_the_row_and_its_history():
    created = _create()
    with session_ctx() as session:
        session.get(ApiKey, created["id"]).last_used_at = datetime.now(timezone.utc)
        session.commit()

    assert client.delete(f"/api_key/{created['id']}").status_code == 204

    with session_ctx() as session:
        row = session.get(ApiKey, created["id"])
        assert row is not None
        assert row.revoked_at is not None
        # The reason the row is kept: you want this after revoking, not before.
        assert row.last_used_at is not None


def test_revoking_twice_leaves_the_original_revocation_time_alone():
    created = _create()
    assert client.delete(f"/api_key/{created['id']}").status_code == 204
    with session_ctx() as session:
        first = session.get(ApiKey, created["id"]).revoked_at

    assert client.delete(f"/api_key/{created['id']}").status_code == 204
    with session_ctx() as session:
        assert session.get(ApiKey, created["id"]).revoked_at == first


def test_revoke_of_another_users_key_is_a_404():
    with session_ctx() as session:
        theirs = _insert_key(session, owner_sub=OTHER_OWNER_SUB)
        theirs_id = theirs.id

    assert client.delete(f"/api_key/{theirs_id}").status_code == 404

    with session_ctx() as session:
        assert session.get(ApiKey, theirs_id).revoked_at is None


# RESOLVER =====================================================================


def test_a_fresh_key_authenticates():
    created = _create()
    with session_ctx() as session:
        principal = resolve_api_key(session, created["token"])

    assert principal is not None
    assert principal.id == created["id"]
    assert principal.owner_sub == OWNER["sub"]
    assert principal.scope == rules.SCOPE_OGC_INTERNAL


def test_a_revoked_key_stops_working_on_the_next_request():
    created = _create()
    token = created["token"]
    with session_ctx() as session:
        assert resolve_api_key(session, token) is not None

    assert client.delete(f"/api_key/{created['id']}").status_code == 204

    # No redeploy, no cache to wait out -- this is the whole point of the table.
    with session_ctx() as session:
        assert resolve_api_key(session, token) is None


def test_an_expired_key_does_not_authenticate():
    token = rules.generate_token()
    with session_ctx() as session:
        _insert_key(
            session,
            token=token,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert resolve_api_key(session, token) is None


def test_an_unknown_or_malformed_secret_does_not_authenticate():
    with session_ctx() as session:
        assert resolve_api_key(session, rules.generate_token()) is None
        assert resolve_api_key(session, "not-a-key") is None
        assert resolve_api_key(session, "") is None


def test_a_near_miss_on_the_token_does_not_authenticate():
    created = _create()
    token = created["token"]
    with session_ctx() as session:
        assert (
            resolve_api_key(session, token[:-1] + ("a" if token[-1] != "a" else "b"))
            is None
        )
        assert resolve_api_key(session, token.upper()) is None


def test_use_refreshes_last_used_at_but_not_on_every_request():
    created = _create()
    token = created["token"]

    with session_ctx() as session:
        assert resolve_api_key(session, token) is not None
        first = session.get(ApiKey, created["id"]).last_used_at
    assert first is not None

    # Within LAST_USED_RESOLUTION, a second use must not pay for a write --
    # desktop clients page through items and would otherwise write per page.
    with session_ctx() as session:
        assert resolve_api_key(session, token) is not None
        assert session.get(ApiKey, created["id"]).last_used_at == first

    # Once it is stale enough, the next use moves it.
    with session_ctx() as session:
        session.get(ApiKey, created["id"]).last_used_at = first - timedelta(hours=2)
        session.commit()
    with session_ctx() as session:
        assert resolve_api_key(session, token) is not None
        assert session.get(ApiKey, created["id"]).last_used_at > first - timedelta(
            hours=2
        )


# ============= EOF =============================================
