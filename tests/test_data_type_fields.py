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
"""Which columns a data-type grant reaches (ADR5, Part III).

The classification is only worth having if a bad one cannot load. These cover
the four ways it can be wrong -- a field claimed twice, a field claimed by
nobody, a term nobody can grant, a field that does not exist -- and the
projection that follows from a good one.
"""

import pytest

from domain.data_type_fields import (
    DuplicateFieldClassification,
    UnclassifiedField,
    UnknownDataType,
    fields_for,
    project_data_types,
    validate_classification,
)
from services.field_projection import (
    LOCATION,
    THING,
    _data_type_configuration,
    data_type_fields,
    data_types_covering,
    project_entity_for_data_types,
    project_response_for_data_types,
    record_fields,
    response_classification,
)

KNOWN_TYPES = ("site metadata", "well construction")


def _validate(always=(), by_data_type=None, known=("id", "name", "well_depth")):
    validate_classification(
        entity="thing",
        always=always,
        by_data_type=by_data_type or {},
        known_fields=known,
        known_data_types=KNOWN_TYPES,
    )


class TestClassificationValidation:
    def test_a_complete_classification_passes(self):
        _validate(
            always=("id",),
            by_data_type={
                "site metadata": ("name",),
                "well construction": ("well_depth",),
            },
        )

    def test_a_field_in_two_data_types_is_rejected(self):
        """Revoking one type would leave the field readable through the other."""
        with pytest.raises(DuplicateFieldClassification):
            _validate(
                always=("id",),
                by_data_type={
                    "site metadata": ("name", "well_depth"),
                    "well construction": ("well_depth",),
                },
            )

    def test_a_field_in_always_and_a_data_type_is_rejected(self):
        """`always` cannot be granted, so the grant would mean nothing."""
        with pytest.raises(DuplicateFieldClassification):
            _validate(
                always=("id", "name"),
                by_data_type={
                    "site metadata": ("name",),
                    "well construction": ("well_depth",),
                },
            )

    def test_an_unclassified_field_is_rejected(self):
        """The new-column case: it stops the process, it does not leak."""
        with pytest.raises(UnclassifiedField) as caught:
            _validate(
                always=("id",),
                by_data_type={"site metadata": ("name",)},
            )
        assert "well_depth" in str(caught.value)

    def test_a_field_that_does_not_exist_is_rejected(self):
        with pytest.raises(UnclassifiedField):
            _validate(
                always=("id", "typo_field"),
                by_data_type={
                    "site metadata": ("name",),
                    "well construction": ("well_depth",),
                },
            )

    def test_a_term_that_is_not_a_data_type_is_rejected(self):
        with pytest.raises(UnknownDataType):
            _validate(
                always=("id",),
                by_data_type={
                    "site metadata": ("name",),
                    "well construction": ("well_depth",),
                    "borehole gossip": (),
                },
            )


class TestFieldsFor:
    def test_no_data_types_leaves_only_always(self):
        assert fields_for(("id",), {"site metadata": ("name",)}, ()) == frozenset(
            {"id"}
        )

    def test_holding_two_types_is_the_union(self):
        reachable = fields_for(
            ("id",),
            {"site metadata": ("name",), "well construction": ("well_depth",)},
            ("site metadata", "well construction"),
        )
        assert reachable == frozenset({"id", "name", "well_depth"})

    def test_an_ungranted_type_adds_nothing(self):
        reachable = fields_for(
            ("id",),
            {"site metadata": ("name",), "well construction": ("well_depth",)},
            ("site metadata",),
        )
        assert "well_depth" not in reachable


class TestProjection:
    def test_withheld_fields_are_absent_not_null(self):
        """Absent says "you may not see this"; null says "there is nothing"."""
        projected = project_data_types(
            {"id": 1, "name": "PW-1", "well_depth": 450},
            frozenset({"id", "name"}),
        )
        assert projected == {"id": 1, "name": "PW-1"}
        assert "well_depth" not in projected


class TestTheRealConfiguration:
    """The file that ships, against the models that ship."""

    def test_it_loads(self):
        assert set(_data_type_configuration()) == {THING, LOCATION}

    @pytest.mark.parametrize("entity", [THING, LOCATION])
    def test_every_record_field_is_classified(self, entity):
        """Exhaustive by construction: adding a column fails this."""
        always, by_data_type = _data_type_configuration()[entity]
        classified = set(always)
        for fields in by_data_type.values():
            classified |= set(fields)
        assert classified == set(record_fields(entity))

    def test_well_construction_reaches_construction_columns(self):
        reachable = data_type_fields(THING, ["well construction"])
        assert "well_depth" in reachable
        assert "well_casing_diameter" in reachable
        # ... and does not reach what site metadata covers.
        assert "name" not in reachable

    def test_site_metadata_reaches_identity_and_place(self):
        assert "name" in data_type_fields(THING, ["site metadata"])
        assert "county" in data_type_fields(LOCATION, ["site metadata"])

    def test_a_caller_with_no_grants_gets_only_record_keeping(self):
        record = {
            "id": 7,
            "name": "PW-1",
            "well_depth": 450,
            "release_status": "public",
        }
        projected = project_entity_for_data_types(THING, record, ())
        assert projected == {"id": 7, "release_status": "public"}

    def test_landowner_notes_are_field_operations_not_site_metadata(self):
        """The interview case: staff free text is not readable by default.

        And it is not reachable by knowing where the well is, either -- site
        metadata gets the county, not the gate code.
        """
        assert "nma_location_notes" not in data_type_fields(LOCATION, ())
        assert "nma_location_notes" not in data_type_fields(LOCATION, ["site metadata"])
        assert "nma_location_notes" in data_type_fields(LOCATION, ["field operations"])

    def test_data_types_covering_names_the_type_or_none_for_always(self):
        assert data_types_covering(THING, "well_depth") == "well construction"
        assert data_types_covering(THING, "name") == "site metadata"
        assert data_types_covering(THING, "id") is None


# ------ end to end, against the grant table ----------


class TestReadableThroughGrants:
    """The whole point: a grant, evaluated, decides which columns come back.

    Not a unit test of the classification -- these write real rows and let
    ``services.visibility.may`` decide, so scope and expiry are exercised by
    the same code a request uses.
    """

    ROLE = "Test.FieldMapRole"

    @pytest.fixture
    def granted(self):
        """Grant a role `read` on one data type, globally, and clean up."""
        from datetime import date

        from db.engine import session_ctx
        from db.permission_grant import PermissionGrant
        from domain.access import (
            CAPABILITY_READ,
            PRINCIPAL_ROLE,
            SCOPE_GLOBAL,
        )
        from sqlalchemy import delete

        def _grant(data_type):
            with session_ctx() as session:
                session.add(
                    PermissionGrant(
                        principal_type=PRINCIPAL_ROLE,
                        principal_id=self.ROLE,
                        capability=CAPABILITY_READ,
                        scope_type=SCOPE_GLOBAL,
                        scope_id=None,
                        data_type=data_type,
                        starts_at=date.today(),
                        granted_by="tests",
                    )
                )
                session.commit()

        yield _grant

        with session_ctx() as session:
            session.execute(
                delete(PermissionGrant).where(PermissionGrant.principal_id == self.ROLE)
            )
            session.commit()

    def _principals(self):
        from services.visibility import principals_from_payload

        return principals_from_payload({"sub": "test-user", "groups": [self.ROLE]})

    def test_a_caller_with_no_grants_reads_only_record_keeping(self, water_well_thing):
        from db.engine import session_ctx
        from services.visibility import readable_thing_record

        with session_ctx() as session:
            record = readable_thing_record(
                session, self._principals(), water_well_thing
            )

        assert record["id"] == water_well_thing.id
        assert "name" not in record
        assert "well_depth" not in record

    def test_site_metadata_alone_withholds_construction(
        self, granted, water_well_thing
    ):
        from db.engine import session_ctx
        from services.visibility import readable_thing_record

        granted("site metadata")

        with session_ctx() as session:
            record = readable_thing_record(
                session, self._principals(), water_well_thing
            )

        assert record["name"] == water_well_thing.name
        assert record["thing_type"] == "water well"
        # The well is 10 ft deep and this caller cannot be told so.
        assert "well_depth" not in record
        assert "well_casing_diameter" not in record

    def test_both_types_read_the_whole_record(self, granted, water_well_thing):
        from db.engine import session_ctx
        from services.visibility import readable_thing_record

        granted("site metadata")
        granted("well construction")

        with session_ctx() as session:
            record = readable_thing_record(
                session, self._principals(), water_well_thing
            )

        assert record["name"] == water_well_thing.name
        assert record["well_depth"] == water_well_thing.well_depth
        assert set(record) == set(record_fields(THING))

    def test_a_revoked_grant_withholds_again(self, granted, water_well_thing):
        """Revocation is read at use: no cache, no token to outlive it."""
        from datetime import datetime, timezone

        from db.engine import session_ctx
        from db.permission_grant import PermissionGrant
        from services.visibility import readable_thing_record
        from sqlalchemy import update

        granted("site metadata")

        with session_ctx() as session:
            assert "name" in readable_thing_record(
                session, self._principals(), water_well_thing
            )

        with session_ctx() as session:
            session.execute(
                update(PermissionGrant)
                .where(PermissionGrant.principal_id == self.ROLE)
                .values(revoked_at=datetime.now(timezone.utc))
            )
            session.commit()

        with session_ctx() as session:
            record = readable_thing_record(
                session, self._principals(), water_well_thing
            )
        assert "name" not in record


# ------ responses, which are not their tables ----------


class TestResponseClassification:
    """WellResponse carries 50 fields; 18 are columns and 32 are not."""

    def test_every_declared_field_resolves(self):
        from schemas.thing import WellResponse

        classification = response_classification("WellResponse")
        assert set(classification) == set(WellResponse.model_fields)

    def test_a_column_backed_field_takes_its_column_type(self):
        assert response_classification("WellResponse")["well_depth"] == (
            "well construction"
        )

    def test_a_unit_follows_the_value_it_measures(self):
        """A unit cannot outlive the number it describes."""
        classification = response_classification("WellResponse")
        assert classification["well_depth_unit"] == classification["well_depth"]

    def test_a_provenance_field_follows_its_value(self):
        classification = response_classification("WellResponse")
        assert classification["well_depth_source"] == classification["well_depth"]

    def test_the_suffix_rule_resolves_through_a_named_field(self):
        """measuring_point_height_unit -> measuring_point_height -> named."""
        classification = response_classification("WellResponse")
        assert classification["measuring_point_height_unit"] == "well construction"

    def test_contacts_are_pii(self):
        assert response_classification("WellResponse")["contacts"] == "pii"

    def test_site_access_consent_and_staff_notes_are_field_operations(self):
        classification = response_classification("WellResponse")
        assert classification["permissions"] == "field operations"
        assert classification["well_location_note"] == "field operations"
        assert classification["site_notes"] == "field operations"

    def test_a_field_nothing_resolves_is_rejected(self):
        from domain.data_type_fields import (
            UnclassifiedResponseField,
            classify_response,
        )

        with pytest.raises(UnclassifiedResponseField):
            classify_response(
                schema_fields=("mystery_field",),
                column_types={"well_depth": "well construction"},
                response_types={},
                pending=frozenset(),
                suffixes=("_unit",),
            )


class TestResponseProjection:
    PAYLOAD = {
        "id": 7,
        "name": "PW-1",
        "well_depth": 450,
        "well_depth_unit": "ft",
        "contacts": [{"name": "A Landowner", "phone": "555-0100"}],
        "permissions": [{"permission_type": "site access"}],
        "well_location_note": ["gate code 1234"],
        "groups": [{"id": 1}],
    }

    def test_site_metadata_alone_withholds_pii_and_field_operations(self):
        projected = project_response_for_data_types(
            "WellResponse", self.PAYLOAD, ["site metadata"]
        )
        assert projected["name"] == "PW-1"
        assert "contacts" not in projected
        assert "permissions" not in projected
        assert "well_location_note" not in projected
        assert "well_depth" not in projected

    def test_pii_reaches_contacts_and_nothing_else(self):
        projected = project_response_for_data_types(
            "WellResponse", self.PAYLOAD, ["pii"]
        )
        assert projected["contacts"] == self.PAYLOAD["contacts"]
        assert "permissions" not in projected
        assert "name" not in projected

    def test_field_operations_reaches_consent_and_notes(self):
        projected = project_response_for_data_types(
            "WellResponse", self.PAYLOAD, ["field operations"]
        )
        assert projected["permissions"] == self.PAYLOAD["permissions"]
        assert projected["well_location_note"] == self.PAYLOAD["well_location_note"]
        assert "contacts" not in projected

    def test_a_unit_travels_with_its_value(self):
        projected = project_response_for_data_types(
            "WellResponse", self.PAYLOAD, ["well construction"]
        )
        assert projected["well_depth"] == 450
        assert projected["well_depth_unit"] == "ft"

    def test_holding_every_data_type_reads_the_whole_payload(self):
        from core.enums import AccessDataType

        projected = project_response_for_data_types(
            "WellResponse",
            self.PAYLOAD,
            [member.value for member in AccessDataType],
        )
        assert projected == self.PAYLOAD

    def test_a_pending_field_reaches_nobody(self):
        """Nothing is pending today; the mechanism still has to hold.

        Tested against a constructed classification rather than the shipped
        one, so classifying the last open field does not delete the guarantee
        that an unanswered question is not a grant.
        """
        from domain.data_type_fields import ALWAYS, WITHHELD, response_fields_for

        classification = {
            "id": ALWAYS,
            "name": "site metadata",
            "mystery": WITHHELD,
        }
        assert response_fields_for(classification, ["site metadata"]) == frozenset(
            {"id", "name"}
        )

    def test_group_membership_is_field_operations(self):
        assert response_classification("WellResponse")["groups"] == "field operations"

    def test_open_status_follows_the_installation_not_the_programme(self):
        classification = response_classification("WellResponse")
        assert classification["open_status"] == "well construction"
        assert classification["monitoring_status"] == "field operations"
        assert classification["datalogger_suitability_status"] == "field operations"

    def test_identifiers_and_aquifers_are_site_metadata(self):
        classification = response_classification("WellResponse")
        assert classification["links"] == "site metadata"
        assert classification["aquifers"] == "site metadata"
