"""Tests for permission_grant validation.

Two layers:

* domain/permission_grant.py's pure checks -- no database, no fixtures.
* services/permission_grant_helper.py's principal_exists -- needs a session,
  since api_key is the one principal_type with a real table to check.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from db.api_key import ApiKey
from db.engine import session_ctx
from domain import api_key as key_rules
from domain.permission_grant import (
    validate_capability,
    validate_principal_type,
    validate_scope_type,
)
from services.permission_grant_helper import principal_exists

OWNER_SUB = "owner-sub-permission-grant-test"


@pytest.fixture(autouse=True)
def clean_keys():
    def _purge():
        with session_ctx() as session:
            for row in session.scalars(
                select(ApiKey).where(ApiKey.owner_sub == OWNER_SUB)
            ).all():
                session.delete(row)
            session.commit()

    _purge()
    yield
    _purge()


def _insert_key(session) -> ApiKey:
    token = key_rules.generate_token()
    now = datetime.now(timezone.utc)
    key = ApiKey(
        token_digest=key_rules.digest_token(token),
        token_preview=key_rules.preview_token(token),
        name="Permission grant test key",
        owner_sub=OWNER_SUB,
        scope=key_rules.SCOPE_OGC_INTERNAL,
        expires_at=key_rules.expiry_for(now),
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return key


# DOMAIN RULES =================================================================


def test_a_valid_capability_passes():
    validate_capability("read")


def test_an_invalid_capability_is_rejected():
    with pytest.raises(ValueError):
        validate_capability("bogus")


def test_a_valid_scope_type_passes():
    validate_scope_type("global")


def test_an_invalid_scope_type_is_rejected():
    with pytest.raises(ValueError):
        validate_scope_type("bogus")


def test_a_valid_principal_type_passes():
    validate_principal_type("api_key")


def test_an_invalid_principal_type_is_rejected():
    with pytest.raises(ValueError):
        validate_principal_type("bogus")


# PRINCIPAL EXISTENCE ===========================================================


def test_an_existing_api_key_exists():
    with session_ctx() as session:
        key = _insert_key(session)
        assert principal_exists(session, "api_key", str(key.id)) is True


def test_a_nonexistent_api_key_does_not_exist():
    with session_ctx() as session:
        assert principal_exists(session, "api_key", "999999999") is False


def test_a_non_numeric_api_key_id_does_not_exist():
    with session_ctx() as session:
        assert principal_exists(session, "api_key", "not-a-number") is False


def test_user_and_principal_group_pass_through_unchecked():
    # No local registry for either yet -- see services/permission_grant_helper.py.
    with session_ctx() as session:
        assert principal_exists(session, "user", "any-jwt-sub") is True
        assert principal_exists(session, "principal_group", "AMP.Viewer") is True


# ============= EOF =============================================
