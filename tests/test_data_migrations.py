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
import importlib

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

move_notes = importlib.import_module(
    "data_migrations.migrations.20260205_0001_move_nma_location_notes"
)
publish_project_areas = importlib.import_module(
    "data_migrations.migrations.20260714_0001_publish_project_areas"
)
backfill_acoustic_maturity = importlib.import_module(
    "data_migrations.migrations.20260820_0001_backfill_acoustic_data_maturity"
)
seed_legacy_access = importlib.import_module(
    "data_migrations.migrations.20260829_0001_seed_legacy_access_grants"
)
from db.authorization_audit import AuthorizationAudit
from db.destination import Destination
from db.location import Location
from db.permission_grant import PermissionGrant
from db.publication_consent import PublicationConsent
from db.thing import Thing
from db.notes import Notes
from db.group import Group
from db.engine import session_ctx
from db.transducer import TransducerObservation
from services.access_seed import SEED_ACTOR, data_types
from tests import get_parameter_id


def test_move_nma_location_notes_creates_notes_and_clears_field():
    with session_ctx() as session:
        location = Location(
            point="POINT (10.2 10.2)",
            elevation=0,
            release_status="public",
            nma_location_notes="Legacy location note",
        )
        session.add(location)
        session.commit()
        session.refresh(location)

        move_notes.run(session)

        notes = (
            session.execute(
                select(Notes).where(
                    Notes.target_table == "location",
                    Notes.target_id == location.id,
                )
            )
            .scalars()
            .all()
        )
        assert len(notes) == 1
        assert notes[0].content == "Legacy location note"
        assert notes[0].note_type == "General"
        assert notes[0].release_status == "public"

        session.refresh(location)
        assert location.nma_location_notes is None

        session.delete(notes[0])
        session.delete(location)
        session.commit()


def test_move_nma_location_notes_skips_duplicates():
    with session_ctx() as session:
        location = Location(
            point="POINT (10.4 10.4)",
            elevation=1.0,
            release_status="draft",
            nma_location_notes="Duplicate note",
        )
        session.add(location)
        session.commit()
        session.refresh(location)

        existing = Notes(
            target_id=location.id,
            target_table="location",
            note_type="General",
            content="Duplicate note",
            release_status="draft",
        )
        session.add(existing)
        session.commit()

        move_notes.run(session)

        notes = (
            session.execute(
                select(Notes).where(
                    Notes.target_table == "location",
                    Notes.target_id == location.id,
                    Notes.note_type == "General",
                )
            )
            .scalars()
            .all()
        )
        assert len(notes) == 1

        session.refresh(location)
        assert location.nma_location_notes is None

        session.delete(notes[0])
        session.delete(location)
        session.commit()


def test_publish_project_areas_marks_project_area_groups_public():
    with session_ctx() as session:
        draft_with_area = Group(
            name="Draft Project Area A",
            description="Has a project area, should be published.",
            release_status="draft",
            project_area="MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, -106.6 34.2, -107.2 34.2, -107.2 33.6)))",
        )
        draft_without_area = Group(
            name="Draft No Area",
            description="No project area, should be left alone.",
            release_status="draft",
        )
        session.add_all([draft_with_area, draft_without_area])
        session.commit()
        session.refresh(draft_with_area)
        session.refresh(draft_without_area)

        publish_project_areas.run(session)

        session.refresh(draft_with_area)
        session.refresh(draft_without_area)
        assert draft_with_area.release_status == "public"
        assert draft_without_area.release_status == "draft"

        session.delete(draft_with_area)
        session.delete(draft_without_area)
        session.commit()


def test_backfill_acoustic_data_maturity_only_touches_null_acoustic_rows(
    sensor_to_water_well_thing_deployment,
):
    deployment_id = sensor_to_water_well_thing_deployment.id
    parameter_id = get_parameter_id("groundwater level", "Field Parameter")
    observed = datetime(2019, 7, 23, 12, 0, tzinfo=timezone.utc)

    with session_ctx() as session:
        # An acoustic row with no maturity -- the case this migration exists for.
        acoustic = TransducerObservation(
            parameter_id=parameter_id,
            deployment_id=deployment_id,
            observation_datetime=observed,
            value=42.0,
            nma_waterlevelscontinuous_acoustic_global_id="ACOUSTIC-NULL",
        )
        # An acoustic row whose maturity was already set deliberately. The
        # blanket value must not overwrite a decision someone made.
        acoustic_already_set = TransducerObservation(
            parameter_id=parameter_id,
            deployment_id=deployment_id,
            observation_datetime=observed + timedelta(hours=1),
            value=43.0,
            nma_waterlevelscontinuous_acoustic_global_id="ACOUSTIC-SET",
            data_maturity="provisional",
        )
        # A pressure row with no maturity. NULL here means the pressure QC flag
        # was NULL, which is a different question -- leave it alone.
        pressure = TransducerObservation(
            parameter_id=parameter_id,
            deployment_id=deployment_id,
            observation_datetime=observed + timedelta(hours=2),
            value=44.0,
            nma_waterlevelscontinuous_pressure_global_id="PRESSURE-NULL",
        )
        session.add_all([acoustic, acoustic_already_set, pressure])
        session.commit()
        ids = (acoustic.id, acoustic_already_set.id, pressure.id)

        try:
            backfill_acoustic_maturity.run(session)

            session.refresh(acoustic)
            session.refresh(acoustic_already_set)
            session.refresh(pressure)
            assert acoustic.data_maturity == backfill_acoustic_maturity.MATURITY
            assert acoustic_already_set.data_maturity == "provisional"
            assert pressure.data_maturity is None
        finally:
            session.execute(
                delete(TransducerObservation).where(TransducerObservation.id.in_(ids))
            )
            session.commit()


def test_backfill_acoustic_data_maturity_is_idempotent(
    sensor_to_water_well_thing_deployment,
):
    deployment_id = sensor_to_water_well_thing_deployment.id
    parameter_id = get_parameter_id("groundwater level", "Field Parameter")

    with session_ctx() as session:
        observation = TransducerObservation(
            parameter_id=parameter_id,
            deployment_id=deployment_id,
            observation_datetime=datetime(2020, 1, 1, tzinfo=timezone.utc),
            value=45.0,
            nma_waterlevelscontinuous_acoustic_global_id="ACOUSTIC-REPEAT",
        )
        session.add(observation)
        session.commit()
        observation_id = observation.id

        try:
            backfill_acoustic_maturity.run(session)
            backfill_acoustic_maturity.run(session)

            session.refresh(observation)
            assert observation.data_maturity == backfill_acoustic_maturity.MATURITY
        finally:
            session.execute(
                delete(TransducerObservation).where(
                    TransducerObservation.id == observation_id
                )
            )
            session.commit()


def _consents_for(session, thing_id):
    return (
        session.execute(
            select(PublicationConsent).where(PublicationConsent.thing_id == thing_id)
        )
        .scalars()
        .all()
    )


def test_grandfathering_covers_public_things_and_leaves_the_rest_alone():
    """release_status='public' already publishes everything about a record, so
    the grandfathered consent is the widest one: every data type."""
    with session_ctx() as session:
        public = Thing(name="Grandfathered Well", thing_type="water well")
        public.release_status = "public"
        private = Thing(name="Unpublished Well", thing_type="water well")
        private.release_status = "draft"
        session.add_all([public, private])
        session.commit()
        public_id, private_id = public.id, private.id

        try:
            seed_legacy_access.run(session)

            granted = _consents_for(session, public_id)
            destinations = {
                row.destination.slug: {
                    consent.data_type
                    for consent in granted
                    if consent.destination_id == row.destination_id
                }
                for row in granted
            }
            assert destinations == {
                spec.slug: set(seed_legacy_access.consented_data_types(spec))
                for spec in seed_legacy_access.BASELINE_DESTINATIONS
            }
            assert all(
                row.recorded_by == seed_legacy_access.GRANDFATHER_ACTOR
                for row in granted
            )
            # Institutional, not a landowner's: no contact is invented.
            assert all(row.contact_id is None for row in granted)
            assert _consents_for(session, private_id) == []
        finally:
            session.execute(
                delete(PublicationConsent).where(
                    PublicationConsent.recorded_by
                    == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(AuthorizationAudit).where(
                    AuthorizationAudit.actor == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(PermissionGrant).where(PermissionGrant.granted_by == SEED_ACTOR)
            )
            session.execute(
                delete(AuthorizationAudit).where(AuthorizationAudit.actor == SEED_ACTOR)
            )
            session.execute(
                delete(Destination).where(
                    Destination.slug.in_(
                        [spec.slug for spec in seed_legacy_access.BASELINE_DESTINATIONS]
                    )
                )
            )
            session.execute(delete(Thing).where(Thing.id.in_([public_id, private_id])))
            session.commit()


def test_grandfathering_twice_writes_nothing_the_second_time():
    with session_ctx() as session:
        thing = Thing(name="Twice Grandfathered Well", thing_type="water well")
        thing.release_status = "public"
        session.add(thing)
        session.commit()
        thing_id = thing.id

        try:
            first = seed_legacy_access._grandfather_public_things(session)
            second = seed_legacy_access._grandfather_public_things(session)
            ngwmn = seed_legacy_access._grandfather_public_things(
                session, seed_legacy_access.NGWMN_DESTINATION
            )

            ngwmn_types = seed_legacy_access.consented_data_types(
                seed_legacy_access.NGWMN_DESTINATION
            )
            assert first >= len(data_types())
            assert second == 0
            assert ngwmn >= len(ngwmn_types)
            assert len(_consents_for(session, thing_id)) == len(data_types()) + len(
                ngwmn_types
            )
        finally:
            session.execute(
                delete(PublicationConsent).where(
                    PublicationConsent.recorded_by
                    == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(AuthorizationAudit).where(
                    AuthorizationAudit.actor == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(Destination).where(
                    Destination.slug.in_(
                        [spec.slug for spec in seed_legacy_access.BASELINE_DESTINATIONS]
                    )
                )
            )
            session.execute(delete(Thing).where(Thing.id == thing_id))
            session.commit()


def test_every_grandfathered_consent_is_audited():
    """No row that changes what is published lands without a trace."""
    with session_ctx() as session:
        thing = Thing(name="Audited Grandfathered Well", thing_type="water well")
        thing.release_status = "public"
        session.add(thing)
        session.commit()
        thing_id = thing.id

        try:
            seed_legacy_access._grandfather_public_things(session)
            consent_ids = {row.id for row in _consents_for(session, thing_id)}
            events = (
                session.execute(
                    select(AuthorizationAudit).where(
                        AuthorizationAudit.subject_id.in_(consent_ids),
                        AuthorizationAudit.subject_table == "publication_consent",
                    )
                )
                .scalars()
                .all()
            )

            assert {event.subject_id for event in events} == consent_ids
            assert {event.event_type for event in events} == {"consent.recorded"}
            assert all(
                event.detail["grandfathered_from"] == "public" for event in events
            )
        finally:
            session.execute(
                delete(PublicationConsent).where(
                    PublicationConsent.recorded_by
                    == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(AuthorizationAudit).where(
                    AuthorizationAudit.actor == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(Destination).where(
                    Destination.slug.in_(
                        [spec.slug for spec in seed_legacy_access.BASELINE_DESTINATIONS]
                    )
                )
            )
            session.execute(delete(Thing).where(Thing.id == thing_id))
            session.commit()


def test_a_destination_registered_under_another_kind_is_refused():
    """The kind picks the field allowlist, so publishing under the wrong one
    would send a different set of fields than anybody chose."""
    spec = seed_legacy_access.NGWMN_DESTINATION
    with session_ctx() as session:
        wrong = Destination(
            slug=spec.slug,
            name=spec.name,
            destination_kind="public web",
            active=True,
        )
        session.add(wrong)
        session.commit()

        try:
            with pytest.raises(seed_legacy_access.DestinationKindConflict):
                seed_legacy_access._destination(session, spec)
        finally:
            session.execute(delete(Destination).where(Destination.slug == spec.slug))
            session.commit()


def test_ngwmn_is_not_grandfathered_for_water_chemistry():
    """The harvester was never offered chemistry. Grandfathering it would hand
    a federal network a data type nobody agreed to send."""
    spec = seed_legacy_access.NGWMN_DESTINATION
    consented = seed_legacy_access.consented_data_types(spec)

    assert "water chemistry" not in consented
    assert set(consented) == set(data_types()) - {"water chemistry"}
    # The public web keeps everything: that is what the column already meant.
    assert set(
        seed_legacy_access.consented_data_types(seed_legacy_access.PUBLIC_DESTINATION)
    ) == set(data_types())


def test_the_excluded_type_is_absent_from_the_rows_written():
    with session_ctx() as session:
        thing = Thing(name="Chemistry Excluded Well", thing_type="water well")
        thing.release_status = "public"
        session.add(thing)
        session.commit()
        thing_id = thing.id

        try:
            seed_legacy_access._grandfather_public_things(
                session, seed_legacy_access.NGWMN_DESTINATION
            )
            written = {
                row.data_type
                for row in _consents_for(session, thing_id)
                if row.destination.slug == "ngwmn"
            }

            assert "water chemistry" not in written
            assert written == set(
                seed_legacy_access.consented_data_types(
                    seed_legacy_access.NGWMN_DESTINATION
                )
            )
        finally:
            session.execute(
                delete(PublicationConsent).where(
                    PublicationConsent.thing_id == thing_id
                )
            )
            session.execute(
                delete(AuthorizationAudit).where(
                    AuthorizationAudit.actor == seed_legacy_access.GRANDFATHER_ACTOR
                )
            )
            session.execute(
                delete(Destination).where(
                    Destination.slug.in_(
                        [spec.slug for spec in seed_legacy_access.BASELINE_DESTINATIONS]
                    )
                )
            )
            session.execute(delete(Thing).where(Thing.id == thing_id))
            session.commit()
