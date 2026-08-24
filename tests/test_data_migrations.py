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
from db.location import Location
from db.notes import Notes
from db.group import Group
from db.engine import session_ctx
from db.transducer import TransducerObservation
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
