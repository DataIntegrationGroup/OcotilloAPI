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

from sqlalchemy import delete, select, update

move_notes = importlib.import_module(
    "data_migrations.migrations.20260205_0001_move_nma_location_notes"
)
publish_project_areas = importlib.import_module(
    "data_migrations.migrations.20260714_0001_publish_project_areas"
)
backfill_acoustic_maturity = importlib.import_module(
    "data_migrations.migrations.20260820_0001_backfill_acoustic_data_maturity"
)
backfill_category_descriptions = importlib.import_module(
    "data_migrations.migrations." "20260901_0001_backfill_lexicon_category_descriptions"
)
consolidate_groups = importlib.import_module(
    "data_migrations.migrations.20260810_0001_consolidate_geographic_area_groups"
)
from db.lexicon import LexiconCategory
from db.location import Location
from db.notes import Notes
from db.group import Group, GroupThingAssociation
from db.thing import Thing
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


def test_backfill_lexicon_category_descriptions_fills_null_and_keeps_edits():
    """A NULL description is filled from the seed; an edited one survives."""
    with session_ctx() as session:
        # conftest seeds the lexicon, so these categories already exist.
        session.execute(
            update(LexiconCategory)
            .where(LexiconCategory.name == "unit")
            .values(description=None)
        )
        session.execute(
            update(LexiconCategory)
            .where(LexiconCategory.name == "spring_type")
            .values(description="HAND EDITED")
        )
        session.commit()

        try:
            backfill_category_descriptions.run(session)

            seeded = backfill_category_descriptions._seed_descriptions()
            assert _description(session, "unit") == seeded["unit"]
            assert _description(session, "spring_type") == "HAND EDITED"
        finally:
            session.execute(
                update(LexiconCategory)
                .where(LexiconCategory.name.in_(["unit", "spring_type"]))
                .values(description=None)
            )
            session.commit()
            backfill_category_descriptions.run(session)


def test_backfill_lexicon_category_descriptions_is_idempotent():
    with session_ctx() as session:
        session.execute(
            update(LexiconCategory)
            .where(LexiconCategory.name == "unit")
            .values(description=None)
        )
        session.commit()

        backfill_category_descriptions.run(session)
        first = _description(session, "unit")
        backfill_category_descriptions.run(session)

        assert _description(session, "unit") == first
        assert first is not None


def _description(session, name):
    return session.execute(
        select(LexiconCategory.description).where(LexiconCategory.name == name)
    ).scalar_one()


# ==============================================================================
# BDMS-1143: consolidate duplicate Geographic Area groups
# ==============================================================================

AREA_A = (
    "MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, -106.6 34.2, -107.2 34.2, -107.2 33.6)))"
)
AREA_B = (
    "MULTIPOLYGON(((-105.2 32.6, -104.6 32.6, -104.6 33.2, -105.2 33.2, -105.2 32.6)))"
)


def _make_thing(session, name):
    thing = Thing(name=name, thing_type="water well", release_status="public")
    session.add(thing)
    session.commit()
    session.refresh(thing)
    return thing


def _link(session, group, thing):
    session.add(GroupThingAssociation(group_id=group.id, thing_id=thing.id))
    session.commit()


def _delete_groups(session, *groups):
    for group in groups:
        existing = session.get(Group, group.id) if group.id is not None else None
        if existing is not None:
            session.delete(existing)
    session.commit()


def test_consolidate_merges_geometry_links_and_children():
    with session_ctx() as session:
        plan_group = Group(name="Consolidate Basin", group_type="Monitoring Plan")
        area_group = Group(
            name="consolidate  basin",  # normalized match: case and spacing differ
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)

        child = Group(
            name="Consolidate Basin Child",
            group_type="Monitoring Plan",
            parent_group_id=area_group.id,
        )
        session.add(child)
        session.commit()
        session.refresh(child)

        shared_thing = _make_thing(session, "Consolidate Well Shared")
        area_only_thing = _make_thing(session, "Consolidate Well Area Only")
        _link(session, plan_group, shared_thing)
        _link(session, area_group, shared_thing)
        _link(session, area_group, area_only_thing)

        area_id = area_group.id
        consolidate_groups.run(session)

        assert session.get(Group, area_id) is None

        session.refresh(plan_group)
        assert plan_group.project_area is not None

        session.refresh(child)
        assert child.parent_group_id == plan_group.id

        linked = set(
            session.scalars(
                select(GroupThingAssociation.thing_id).where(
                    GroupThingAssociation.group_id == plan_group.id
                )
            ).all()
        )
        assert linked == {shared_thing.id, area_only_thing.id}

        _delete_groups(session, child, plan_group)
        session.delete(session.get(Thing, shared_thing.id))
        session.delete(session.get(Thing, area_only_thing.id))
        session.commit()


def test_consolidate_reports_conflicting_project_area_and_changes_nothing():
    with session_ctx() as session:
        plan_group = Group(
            name="Conflict Basin",
            group_type="Monitoring Plan",
            project_area=AREA_A,
        )
        area_group = Group(
            name="Conflict Basin",
            group_type="Geographic Area",
            project_area=AREA_B,
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)

        plan = consolidate_groups.build_plan(session)
        conflicts = [
            item for item in plan.conflicts if item.geographic_area_id == area_group.id
        ]
        assert len(conflicts) == 1
        assert "already" in conflicts[0].reason
        assert all(merge.geographic_area_id != area_group.id for merge in plan.merges)

        consolidate_groups.run(session)
        assert session.get(Group, area_group.id) is not None

        _delete_groups(session, area_group, plan_group)


def test_consolidate_leaves_unmatched_geographic_area_and_reports_it():
    with session_ctx() as session:
        area_group = Group(
            name="Orphan Geographic Area",
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add(area_group)
        session.commit()
        session.refresh(area_group)

        plan = consolidate_groups.build_plan(session)
        unmatched = [
            item for item in plan.unmatched if item.geographic_area_id == area_group.id
        ]
        assert len(unmatched) == 1
        assert unmatched[0].reason == "no matching group"

        consolidate_groups.run(session)
        assert session.get(Group, area_group.id) is not None

        _delete_groups(session, area_group)


def test_consolidate_is_idempotent():
    with session_ctx() as session:
        plan_group = Group(name="Idempotent Basin", group_type="Monitoring Plan")
        area_group = Group(
            name="Idempotent Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)
        area_id = area_group.id

        consolidate_groups.run(session)
        consolidate_groups.run(session)

        assert session.get(Group, area_id) is None
        session.refresh(plan_group)
        assert plan_group.project_area is not None

        _delete_groups(session, plan_group)


def test_consolidate_dry_run_writes_nothing():
    with session_ctx() as session:
        plan_group = Group(name="Preview Basin", group_type="Monitoring Plan")
        area_group = Group(
            name="Preview Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)

        plan = consolidate_groups.dry_run(session)
        merges = [
            merge for merge in plan.merges if merge.geographic_area_id == area_group.id
        ]
        assert len(merges) == 1
        assert merges[0].target_id == plan_group.id
        assert merges[0].copies_geometry is True

        assert session.get(Group, area_group.id) is not None
        session.refresh(plan_group)
        assert plan_group.project_area is None

        _delete_groups(session, area_group, plan_group)


def test_consolidate_merges_into_untyped_group():
    """A project's row may be left untyped, and is still a valid target."""
    with session_ctx() as session:
        untyped = Group(name="Untyped Target Basin", group_type=None)
        area_group = Group(
            name="Untyped Target Basin Area",
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add_all([untyped, area_group])
        session.commit()
        session.refresh(untyped)
        session.refresh(area_group)
        area_id = area_group.id

        consolidate_groups.MANUAL_MATCHES["Untyped Target Basin Area"] = (
            "Untyped Target Basin"
        )
        try:
            consolidate_groups.run(session)
        finally:
            consolidate_groups.MANUAL_MATCHES.pop("Untyped Target Basin Area")

        assert session.get(Group, area_id) is None
        session.refresh(untyped)
        assert untyped.project_area is not None
        # The target keeps whatever type it had; merging does not retype it.
        assert untyped.group_type is None

        _delete_groups(session, untyped)


def test_consolidate_refuses_protected_geographic_area():
    """A Geographic Area named after a legacy project is that project's row."""
    protected_name = sorted(consolidate_groups.PROTECTED_NAMES)[0]
    with session_ctx() as session:
        plan_group = Group(name="Protected Decoy Plan", group_type="Monitoring Plan")
        area_group = Group(
            name=protected_name,
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)

        # Even an explicit manual mapping must not get past the guard.
        consolidate_groups.MANUAL_MATCHES[protected_name] = "Protected Decoy Plan"
        try:
            plan = consolidate_groups.build_plan(session)
            consolidate_groups.run(session)
        finally:
            consolidate_groups.MANUAL_MATCHES.pop(protected_name)

        protected = [
            item for item in plan.protected if item.geographic_area_id == area_group.id
        ]
        assert len(protected) == 1
        assert "legacy project name" in protected[0].reason
        assert all(merge.geographic_area_id != area_group.id for merge in plan.merges)

        assert session.get(Group, area_group.id) is not None
        session.refresh(plan_group)
        assert plan_group.project_area is None

        _delete_groups(session, area_group, plan_group)


def test_consolidate_refuses_two_areas_claiming_one_target():
    """Sequential merges into one target would silently drop all but the first."""
    with session_ctx() as session:
        target = Group(name="Contested Basin", group_type="Monitoring Plan")
        first = Group(
            name="Contested Basin North",
            group_type="Geographic Area",
            project_area=AREA_A,
        )
        second = Group(
            name="Contested Basin South",
            group_type="Geographic Area",
            project_area=AREA_B,
        )
        session.add_all([target, first, second])
        session.commit()
        for group in (target, first, second):
            session.refresh(group)

        consolidate_groups.MANUAL_MATCHES["Contested Basin North"] = "Contested Basin"
        consolidate_groups.MANUAL_MATCHES["Contested Basin South"] = "Contested Basin"
        try:
            plan = consolidate_groups.build_plan(session)
            consolidate_groups.run(session)
        finally:
            consolidate_groups.MANUAL_MATCHES.pop("Contested Basin North")
            consolidate_groups.MANUAL_MATCHES.pop("Contested Basin South")

        contested = {first.id, second.id}
        assert not contested & {m.geographic_area_id for m in plan.merges}
        flagged = {
            item.geographic_area_id
            for item in plan.ambiguous
            if "also claimed by" in item.reason
        }
        assert contested <= flagged

        assert session.get(Group, first.id) is not None
        assert session.get(Group, second.id) is not None
        session.refresh(target)
        assert target.project_area is None

        _delete_groups(session, first, second, target)
