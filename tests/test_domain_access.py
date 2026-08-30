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
"""Access-control rules (ADR5). No database, no fixtures."""

from datetime import date, datetime, timezone

import pytest

from domain.access import (
    AccessRequest,
    CAPABILITIES,
    CapabilitySubjectMismatch,
    DATA_CAPABILITIES,
    SURFACE_CAPABILITIES,
    PRINCIPAL_TYPES,
    SCOPE_TYPES,
    AmbiguousGrantSubject,
    BackwardsDateRange,
    Consent,
    Grant,
    MissingDataType,
    ScopedSurfaceGrant,
    ScopeIdMismatch,
    UnknownCapability,
    UnknownPrincipalType,
    UnknownScopeType,
    any_consent_publishes,
    any_grant_allows,
    consent_covers,
    grant_covers,
    is_active,
    scope_covers,
    validate_grant,
)

TODAY = date(2026, 8, 24)
STUDENT = ("user", "authentik-sub-1")
EDITOR_ROLE = ("role", "AMP.Editor")


def a_grant(**overrides):
    fields = {
        "principal_type": "user",
        "principal_id": "authentik-sub-1",
        "capability": "read",
        "scope_type": "thing",
        "scope_id": 7,
        "data_type": "water level",
        "starts_at": date(2026, 1, 1),
        "ends_at": None,
        "revoked_at": None,
    }
    fields.update(overrides)
    return Grant(**fields)


def a_request(**overrides):
    fields = {
        "capability": "read",
        "data_type": "water level",
        "principals": (STUDENT,),
        "thing_id": 7,
        "group_ids": (),
    }
    fields.update(overrides)
    return AccessRequest(**fields)


# ------ default deny ----------


def test_no_grants_is_a_no():
    assert any_grant_allows([], a_request(), TODAY) is False


def test_no_principals_is_a_no():
    assert any_grant_allows([a_grant()], a_request(principals=()), TODAY) is False


def test_a_matching_grant_allows():
    assert any_grant_allows([a_grant()], a_request(), TODAY) is True


# ------ every axis has to match ----------


@pytest.mark.parametrize(
    "override",
    [
        {"capability": "correct"},
        {"data_type": "water chemistry"},
        {"principal_id": "somebody-else"},
        {"scope_id": 8},
    ],
)
def test_one_axis_off_denies(override):
    assert grant_covers(a_grant(**override), a_request(), TODAY) is False


def test_principal_type_is_part_of_identity():
    """A role named the same as a subject is not the same principal."""
    grant = a_grant(principal_type="role", principal_id="authentik-sub-1")
    assert grant_covers(grant, a_request(), TODAY) is False


def test_a_role_grant_covers_a_caller_holding_that_role():
    grant = a_grant(principal_type="role", principal_id="AMP.Editor")
    request = a_request(principals=(STUDENT, EDITOR_ROLE))
    assert grant_covers(grant, request, TODAY) is True


# ------ scope ----------


def test_global_scope_reaches_everything():
    assert scope_covers("global", None, thing_id=999, group_ids=()) is True


def test_group_scope_reaches_a_member_thing():
    assert scope_covers("group", 3, thing_id=7, group_ids=(3, 4)) is True


def test_group_scope_stops_at_a_non_member():
    assert scope_covers("group", 3, thing_id=7, group_ids=(4,)) is False


def test_thing_scope_needs_a_thing():
    assert scope_covers("thing", 7, thing_id=None, group_ids=()) is False


def test_an_unknown_scope_type_denies_rather_than_raising():
    """A row written by newer code must not read as permission to older code."""
    assert scope_covers("watershed", 1, thing_id=7, group_ids=()) is False


# ------ time ----------


def test_a_grant_is_dead_before_it_starts():
    assert is_active(date(2026, 9, 1), None, None, TODAY) is False


def test_a_grant_is_dead_after_it_ends():
    assert is_active(date(2026, 1, 1), date(2026, 8, 23), None, TODAY) is False


def test_a_grant_is_live_on_its_last_day():
    assert is_active(date(2026, 1, 1), TODAY, None, TODAY) is True


def test_revocation_beats_the_date_range():
    revoked = datetime(2026, 8, 20, tzinfo=timezone.utc)
    assert is_active(date(2026, 1, 1), None, revoked, TODAY) is False


def test_expiry_is_checked_at_use_not_swept():
    """The same row answers differently on different days, with no job run."""
    semester = a_grant(starts_at=date(2026, 1, 1), ends_at=date(2026, 5, 15))
    assert grant_covers(semester, a_request(), date(2026, 5, 15)) is True
    assert grant_covers(semester, a_request(), date(2026, 5, 16)) is False


# ------ validation, before a row is written ----------


def test_a_grant_without_a_data_type_is_rejected():
    """The no-wildcard rule: NULL does not mean 'all'."""
    with pytest.raises(MissingDataType):
        validate_grant("user", "read", "global", None, None, TODAY, None)


def test_a_global_grant_carries_no_scope_id():
    with pytest.raises(ScopeIdMismatch):
        validate_grant("user", "read", "global", 7, "water level", TODAY, None)


def test_a_thing_grant_needs_a_scope_id():
    with pytest.raises(ScopeIdMismatch):
        validate_grant("user", "read", "thing", None, "water level", TODAY, None)


def test_an_unknown_capability_is_rejected():
    with pytest.raises(UnknownCapability):
        validate_grant("user", "delete", "global", None, "water level", TODAY, None)


def test_an_unknown_principal_type_is_rejected():
    with pytest.raises(UnknownPrincipalType):
        validate_grant("robot", "read", "global", None, "water level", TODAY, None)


def test_an_unknown_scope_type_is_rejected():
    with pytest.raises(UnknownScopeType):
        validate_grant("user", "read", "watershed", 1, "water level", TODAY, None)


def test_a_backwards_date_range_is_rejected():
    with pytest.raises(BackwardsDateRange):
        validate_grant(
            "user", "read", "global", None, "water level", TODAY, date(2026, 1, 1)
        )


def test_validation_errors_are_value_errors():
    """The importers and the routes both rely on this (ADR4)."""
    with pytest.raises(ValueError):
        validate_grant("user", "read", "global", None, None, TODAY, None)


# ------ the domain constants and the lexicon must agree ----------


def test_the_domain_vocabularies_match_the_lexicon():
    """domain/access.py cannot import the lexicon without taking a database
    dependency, so its constants are hand-copied. They drifted once: the
    lexicon says `api key` and the constant said `api_key`, which made every
    API-key grant fail validation with a 422. This is the guard."""
    from core.enums import Capability, GrantScopeType, PrincipalType

    assert {member.value for member in PrincipalType} == set(PRINCIPAL_TYPES)
    assert {member.value for member in Capability} == set(CAPABILITIES)
    assert {member.value for member in GrantScopeType} == set(SCOPE_TYPES)


def test_an_api_key_grant_can_actually_be_written():
    validate_grant("api key", "read", "global", None, "water level", TODAY, None)


# ------ publication consent ----------


def a_consent(**overrides):
    fields = {
        "thing_id": 7,
        "destination_id": 2,
        "data_type": "water level",
        "starts_at": date(2026, 1, 1),
        "ends_at": None,
        "revoked_at": None,
    }
    fields.update(overrides)
    return Consent(**fields)


def test_consent_publishes_the_type_it_names():
    assert consent_covers(a_consent(), 7, 2, "water level", TODAY) is True


def test_consent_to_levels_is_not_consent_to_chemistry():
    """The case the whole design exists for."""
    assert consent_covers(a_consent(), 7, 2, "water chemistry", TODAY) is False


def test_consent_is_per_destination():
    assert consent_covers(a_consent(), 7, 3, "water level", TODAY) is False


def test_withdrawn_consent_stops_being_offered_immediately():
    withdrawn = a_consent(revoked_at=datetime(2026, 8, 24, tzinfo=timezone.utc))
    assert any_consent_publishes([withdrawn], 7, 2, "water level", TODAY) is False


def test_nothing_published_without_a_consent_row():
    assert any_consent_publishes([], 7, 2, "water level", TODAY) is False


# ------ UI-surface grants ----------
#
# A grant reaches data, or it opens a screen. These pin the XOR and the
# global-only rule, and that a data grant never answers a screen question.


def a_surface_grant(**overrides):
    fields = {
        "principal_type": "user",
        "principal_id": "authentik-sub-1",
        "capability": "read",
        "scope_type": "global",
        "scope_id": None,
        "data_type": None,
        "ui_surface": "ocotillo.lexicon",
        "starts_at": date(2026, 1, 1),
        "ends_at": None,
        "revoked_at": None,
    }
    fields.update(overrides)
    return Grant(**fields)


def a_surface_request(**overrides):
    fields = {
        "capability": "read",
        "data_type": None,
        "ui_surface": "ocotillo.lexicon",
        "principals": (STUDENT,),
        "thing_id": None,
        "group_ids": (),
    }
    fields.update(overrides)
    return AccessRequest(**fields)


def test_a_surface_grant_opens_that_screen():
    assert any_grant_allows([a_surface_grant()], a_surface_request(), TODAY) is True


def test_a_surface_grant_does_not_open_another_screen():
    assert (
        grant_covers(
            a_surface_grant(),
            a_surface_request(ui_surface="ocotillo.location"),
            TODAY,
        )
        is False
    )


def test_a_data_grant_does_not_answer_a_screen_question():
    """Both carry None on the axis not being asked about; None must not match."""
    assert grant_covers(a_grant(), a_surface_request(), TODAY) is False


def test_a_surface_grant_does_not_answer_a_data_question():
    assert grant_covers(a_surface_grant(), a_request(), TODAY) is False


def test_a_request_naming_neither_subject_is_a_no():
    """A question this layer cannot answer is not a yes."""
    assert (
        any_grant_allows(
            [a_grant(), a_surface_grant()],
            a_surface_request(ui_surface=None, data_type=None),
            TODAY,
        )
        is False
    )


def test_a_surface_grant_expires_like_any_other():
    grant = a_surface_grant(ends_at=date(2026, 8, 23))
    assert grant_covers(grant, a_surface_request(), TODAY) is False


def test_a_surface_grant_is_dead_once_revoked():
    grant = a_surface_grant(revoked_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    assert grant_covers(grant, a_surface_request(), TODAY) is False


# ------ validation of the two subjects ----------


def test_a_grant_naming_both_subjects_is_rejected():
    """Two grants in one row would share a revocation."""
    with pytest.raises(AmbiguousGrantSubject):
        validate_grant(
            "user",
            "read",
            "global",
            None,
            "water level",
            TODAY,
            None,
            ui_surface="ocotillo.lexicon",
        )


def test_a_grant_naming_neither_subject_is_rejected():
    with pytest.raises(MissingDataType):
        validate_grant("user", "read", "global", None, None, TODAY, None)


def test_a_surface_grant_is_accepted_without_a_data_type():
    validate_grant(
        "user",
        "view",
        "global",
        None,
        None,
        TODAY,
        None,
        ui_surface="ocotillo.lexicon",
    )


@pytest.mark.parametrize("scope_type,scope_id", [("thing", 7), ("group", 3)])
def test_a_scoped_surface_grant_is_rejected(scope_type, scope_id):
    """It could never match: the UI never asks about a screen for one thing."""
    with pytest.raises(ScopedSurfaceGrant):
        validate_grant(
            "user",
            "view",
            scope_type,
            scope_id,
            None,
            TODAY,
            None,
            ui_surface="ocotillo.lexicon",
        )


def test_a_screen_cannot_be_granted_with_a_data_verb():
    """`read` over a screen would be a second spelling of `view`, and the UI
    only ever asks about one of them."""
    with pytest.raises(CapabilitySubjectMismatch):
        validate_grant(
            "user",
            "read",
            "global",
            None,
            None,
            TODAY,
            None,
            ui_surface="ocotillo.lexicon",
        )


def test_data_cannot_be_granted_with_the_screen_verb():
    with pytest.raises(CapabilitySubjectMismatch):
        validate_grant("user", "view", "global", None, "water level", TODAY, None)


def test_the_two_capability_sets_do_not_overlap():
    assert DATA_CAPABILITIES.isdisjoint(SURFACE_CAPABILITIES)
    assert CAPABILITIES == DATA_CAPABILITIES | SURFACE_CAPABILITIES


# ============= EOF =============================================
