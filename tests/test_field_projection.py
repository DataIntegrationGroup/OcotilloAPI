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
"""Field projection (ADR5, 3.5).

The rule tests need no database. The loader tests import the models to know
what fields exist, but never connect.
"""

import pytest

from domain.field_projection import (
    EntityProjection,
    NeverPublicFieldAllowed,
    UnknownField,
    UnknownTransform,
    project,
    round_to,
    validate_projection,
)
from services.field_projection import (
    LOCATION,
    THING,
    _build_projection,
    _configuration,
    known_fields,
    never_public_fields,
    projection_for,
)

RECORD = {
    "id": 1,
    "name": "Test Well",
    "well_depth": 120.0,
    "created_by_id": "authentik-sub-1",
    "nma_pk_welldata": 4321,
}


class FakeDestination:
    def __init__(self, slug, destination_kind):
        self.slug = slug
        self.destination_kind = destination_kind


# ------ the allowlist ----------


def test_only_listed_fields_survive():
    projection = EntityProjection(fields=frozenset({"id", "name"}))
    assert project(RECORD, projection) == {"id": 1, "name": "Test Well"}


def test_a_field_nobody_listed_is_absent_not_null():
    """Omission produces silence: the key is gone, not set to None."""
    projection = EntityProjection(fields=frozenset({"id"}))
    assert "well_depth" not in project(RECORD, projection)


def test_no_projection_publishes_nothing():
    """Default deny. An audience with no rule receives an empty record."""
    assert project(RECORD, None) == {}


def test_a_new_field_is_invisible_until_someone_lists_it():
    projection = EntityProjection(fields=frozenset({"id", "name"}))
    with_new_column = dict(RECORD, gate_code="1234")
    assert "gate_code" not in project(with_new_column, projection)


# ------ never-public ----------


def test_never_public_beats_an_allowlist_that_asked_for_it():
    """Belt and braces: enforced at load, and again at projection time."""
    projection = EntityProjection(fields=frozenset({"id", "created_by_id"}))
    projected = project(RECORD, projection, never_public=frozenset({"created_by_id"}))
    assert projected == {"id": 1}


def test_configuring_a_never_public_field_raises_at_load():
    with pytest.raises(NeverPublicFieldAllowed):
        validate_projection(
            entity=THING,
            fields=["id", "created_by_id"],
            transforms={},
            known_fields=known_fields(THING),
            never_public=frozenset({"created_by_id"}),
        )


def test_provenance_columns_are_never_public():
    assert "created_by_id" in never_public_fields(THING)
    assert "updated_by_name" in never_public_fields(THING)


def test_staff_written_location_notes_are_never_public():
    """Gate codes and candid landowner notes have landed in these columns."""
    assert "nma_location_notes" in never_public_fields(LOCATION)
    assert "nma_coordinate_notes" in never_public_fields(LOCATION)


# ------ transformation ----------


def test_a_coordinate_can_be_rounded_rather_than_dropped():
    projection = EntityProjection(
        fields=frozenset({"latitude"}), transforms={"latitude": ("round", 2)}
    )
    assert project({"latitude": 33.809712}, projection) == {"latitude": 33.81}


def test_rounding_leaves_a_missing_coordinate_missing():
    assert round_to(None, 2) is None


def test_an_untransformed_field_passes_through():
    projection = EntityProjection(
        fields=frozenset({"latitude", "elevation"}),
        transforms={"latitude": ("round", 2)},
    )
    projected = project({"latitude": 33.809712, "elevation": 2464.9}, projection)
    assert projected["elevation"] == 2464.9


# ------ configuration validation ----------


def test_an_unknown_field_raises():
    """A typo in an allowlist silently withholds data, so it fails loudly."""
    with pytest.raises(UnknownField):
        _build_projection(THING, ["id", "welll_depth"], {})


def test_an_unknown_entity_raises():
    with pytest.raises(KeyError):
        _build_projection("borehole", ["id"], {})


def test_an_unknown_transform_raises():
    with pytest.raises(UnknownTransform):
        _build_projection(
            LOCATION,
            {"fields": ["latitude"], "transforms": {"latitude": {"fuzz": 2}}},
            {},
        )


def test_a_transform_on_an_unpublished_field_raises():
    with pytest.raises(UnknownField):
        _build_projection(
            LOCATION, {"fields": ["id"], "transforms": {"latitude": {"round": 2}}}, {}
        )


def test_the_shipped_configuration_is_valid():
    """Loading validates every audience; this asserts it stays that way."""
    assert _configuration()["audiences"]


# ------ audience lookup ----------


def test_a_destination_inherits_the_rules_for_its_kind():
    projection = projection_for(FakeDestination("ngwmn", "harvester"), THING)
    assert "name" in projection.fields


def test_an_unregistered_kind_receives_nothing():
    assert projection_for(FakeDestination("mystery", "carrier pigeon"), THING) is None


def test_the_public_web_gets_a_coarser_coordinate_than_a_harvester():
    public = projection_for(FakeDestination("web", "public web"), LOCATION)
    harvester = projection_for(FakeDestination("ngwmn", "harvester"), LOCATION)
    assert public.transforms["latitude"] == ("round", 2)
    assert harvester.transforms["latitude"] == ("round", 4)
