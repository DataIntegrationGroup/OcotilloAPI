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
from contextlib import contextmanager
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


def test_consolidate_publishes_draft_target_inheriting_public_area():
    """ogc_project_areas filters on release_status, so the boundary must stay
    public when the row carrying it is deleted."""
    with session_ctx() as session:
        plan_group = Group(name="Publish Basin", group_type="Monitoring Plan")
        area_group = Group(
            name="Publish Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add_all([plan_group, area_group])
        session.commit()
        session.refresh(plan_group)
        session.refresh(area_group)
        assert plan_group.release_status == "draft"

        consolidate_groups.run(session)

        assert session.get(Group, area_group.id) is None
        session.refresh(plan_group)
        assert plan_group.project_area is not None
        assert plan_group.release_status == "public"

        _delete_groups(session, plan_group)


def test_consolidate_does_not_demote_public_target():
    """Consolidation only ever raises visibility, so a draft Geographic Area
    cannot pull a published project back off the layer."""
    with session_ctx() as session:
        plan_group = Group(
            name="Demote Basin",
            group_type="Monitoring Plan",
            release_status="public",
        )
        area_group = Group(
            name="Demote Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="draft",
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
        assert merges[0].publishes_target is False

        consolidate_groups.run(session)

        session.refresh(plan_group)
        assert plan_group.release_status == "public"

        _delete_groups(session, plan_group)


def test_consolidate_publishes_target_when_geometry_already_matches():
    """Identical geometries copy nothing, but the public row is still deleted,
    so the target still has to be published."""
    with session_ctx() as session:
        plan_group = Group(
            name="Twin Geometry Basin",
            group_type="Monitoring Plan",
            project_area=AREA_A,
        )
        area_group = Group(
            name="Twin Geometry Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
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
        assert merges[0].copies_geometry is False
        assert merges[0].publishes_target is True

        consolidate_groups.run(session)

        assert session.get(Group, area_group.id) is None
        session.refresh(plan_group)
        assert plan_group.release_status == "public"

        _delete_groups(session, plan_group)


def test_consolidate_dry_run_reports_publish_without_writing():
    with session_ctx() as session:
        plan_group = Group(name="Preview Publish Basin", group_type="Monitoring Plan")
        area_group = Group(
            name="Preview Publish Basin",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
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
        assert merges[0].publishes_target is True

        session.refresh(plan_group)
        assert plan_group.release_status == "draft"

        _delete_groups(session, area_group, plan_group)


# ==============================================================================
# BDMS-1143: the duplicate-project pre-pass
# ==============================================================================


@contextmanager
def _operations(*operations):
    """Swap in a table naming only this test's rows, so nothing real is touched."""
    original = consolidate_groups.DUPLICATE_PLAN_OPERATIONS
    consolidate_groups.DUPLICATE_PLAN_OPERATIONS = tuple(operations)
    try:
        yield
    finally:
        consolidate_groups.DUPLICATE_PLAN_OPERATIONS = original


def _operation(keep_name, delete_name, membership, rename_to=None, **kw):
    return consolidate_groups.DuplicatePlanOperation(
        keep_name=keep_name,
        delete_name=delete_name,
        group_type=kw.pop("group_type", "Monitoring Plan"),
        membership=membership,
        rename_to=rename_to,
        expected_keep_id=kw.pop("expected_keep_id", None),
        expected_delete_id=kw.pop("expected_delete_id", None),
        note="test",
    )


def _linked_thing_ids(session, group_id):
    return set(
        session.scalars(
            select(GroupThingAssociation.thing_id).where(
                GroupThingAssociation.group_id == group_id
            )
        ).all()
    )


def test_prepass_merges_identical_plans_and_renames_survivor():
    with session_ctx() as session:
        keep = Group(name="Prepass Keep", group_type="Monitoring Plan")
        drop = Group(name="Prepass Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        first = _make_thing(session, "Prepass Well One")
        second = _make_thing(session, "Prepass Well Two")
        for group in (keep, drop):
            _link(session, group, first)
            _link(session, group, second)

        drop_id = drop.id
        with _operations(
            _operation("Prepass Keep", "Prepass Drop", "identical", "Prepass Renamed")
        ):
            consolidate_groups.run(session)

        assert session.get(Group, drop_id) is None
        session.refresh(keep)
        assert keep.name == "Prepass Renamed"
        assert _linked_thing_ids(session, keep.id) == {first.id, second.id}

        _delete_groups(session, keep)
        session.delete(session.get(Thing, first.id))
        session.delete(session.get(Thing, second.id))
        session.commit()


def test_prepass_merges_subset_plan_without_duplicating_links():
    with session_ctx() as session:
        keep = Group(name="Subset Keep", group_type="Monitoring Plan")
        drop = Group(name="Subset Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        shared = _make_thing(session, "Subset Well Shared")
        extra = _make_thing(session, "Subset Well Extra")
        _link(session, keep, shared)
        _link(session, keep, extra)
        _link(session, drop, shared)

        drop_id = drop.id
        with _operations(_operation("Subset Keep", "Subset Drop", "superset")):
            consolidate_groups.run(session)

        assert session.get(Group, drop_id) is None
        links = session.scalars(
            select(GroupThingAssociation.thing_id).where(
                GroupThingAssociation.group_id == keep.id
            )
        ).all()
        # The shared link is dropped rather than re-pointed, so it stays single.
        assert sorted(links) == sorted([shared.id, extra.id])

        _delete_groups(session, keep)
        session.delete(session.get(Thing, shared.id))
        session.delete(session.get(Thing, extra.id))
        session.commit()


def test_prepass_merges_disjoint_plans_and_unions_membership():
    with session_ctx() as session:
        keep = Group(name="Disjoint Keep", group_type="Monitoring Plan")
        drop = Group(name="Disjoint Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        mine = _make_thing(session, "Disjoint Well Mine")
        yours = _make_thing(session, "Disjoint Well Yours")
        _link(session, keep, mine)
        _link(session, drop, yours)

        drop_id = drop.id
        with _operations(_operation("Disjoint Keep", "Disjoint Drop", "disjoint")):
            consolidate_groups.run(session)

        assert session.get(Group, drop_id) is None
        assert _linked_thing_ids(session, keep.id) == {mine.id, yours.id}

        _delete_groups(session, keep)
        session.delete(session.get(Thing, mine.id))
        session.delete(session.get(Thing, yours.id))
        session.commit()


def test_prepass_rename_only_operation_renames_without_deleting():
    with session_ctx() as session:
        keep = Group(name="Rename Only", group_type="Monitoring Plan")
        session.add(keep)
        session.commit()
        session.refresh(keep)

        with _operations(_operation("Rename Only", None, "none", "Rename Only Reach")):
            consolidate_groups.run(session)

        session.refresh(keep)
        assert keep.name == "Rename Only Reach"

        _delete_groups(session, keep)


def test_prepass_rename_lets_geographic_area_pass_find_its_target():
    """The Tiffany case: the area can only match a name the pre-pass creates."""
    with session_ctx() as session:
        keep = Group(name="Ordering Restoration", group_type="Monitoring Plan")
        drop = Group(name="Ordering Recovery", group_type="Monitoring Plan")
        area = Group(
            name="Ordering Fire",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add_all([keep, drop, area])
        session.commit()
        for group in (keep, drop, area):
            session.refresh(group)

        well = _make_thing(session, "Ordering Well")
        _link(session, keep, well)
        _link(session, drop, well)

        area_id, drop_id = area.id, drop.id
        with _operations(
            _operation(
                "Ordering Restoration",
                "Ordering Recovery",
                "identical",
                "Ordering Fire",
            )
        ):
            plan = consolidate_groups.dry_run(session)
            assert len(plan.plan_merges) == 1
            assert [merge.target_id for merge in plan.merges] == [keep.id]
            # Nothing written yet.
            session.refresh(keep)
            assert keep.name == "Ordering Restoration"
            assert session.get(Group, area_id) is not None

            consolidate_groups.run(session)

        assert session.get(Group, drop_id) is None
        assert session.get(Group, area_id) is None
        session.refresh(keep)
        assert keep.name == "Ordering Fire"
        assert keep.group_type == "Monitoring Plan"
        assert keep.project_area is not None
        assert keep.release_status == "public"
        assert _linked_thing_ids(session, keep.id) == {well.id}

        _delete_groups(session, keep)
        session.delete(session.get(Thing, well.id))
        session.commit()


def test_prepass_allows_rename_when_only_a_geographic_area_holds_the_name():
    """uq_group_name_type is on the pair, so a Geographic Area is not a clash."""
    with session_ctx() as session:
        keep = Group(name="Pair Keep", group_type="Monitoring Plan")
        area = Group(
            name="Pair Target", group_type="Geographic Area", project_area=AREA_A
        )
        session.add_all([keep, area])
        session.commit()
        session.refresh(keep)
        session.refresh(area)

        with _operations(_operation("Pair Keep", None, "none", "Pair Target")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_merges) == 1, plan.plan_refused

        _delete_groups(session, area, keep)


def test_prepass_refuses_when_rename_target_pair_is_taken():
    with session_ctx() as session:
        keep = Group(name="Taken Keep", group_type="Monitoring Plan")
        blocker = Group(name="Taken Target", group_type="Monitoring Plan")
        session.add_all([keep, blocker])
        session.commit()
        session.refresh(keep)
        session.refresh(blocker)

        with _operations(_operation("Taken Keep", None, "none", "Taken Target")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "uq_group_name_type" in plan.plan_refused[0].reason

            consolidate_groups.run(session)

        session.refresh(keep)
        assert keep.name == "Taken Keep"

        _delete_groups(session, blocker, keep)


def test_prepass_refuses_when_membership_expectation_violated():
    with session_ctx() as session:
        keep = Group(name="Violated Keep", group_type="Monitoring Plan")
        drop = Group(name="Violated Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        shared = _make_thing(session, "Violated Well Shared")
        stray = _make_thing(session, "Violated Well Stray")
        _link(session, keep, shared)
        _link(session, drop, shared)
        _link(session, drop, stray)  # breaks "identical"

        drop_id = drop.id
        with _operations(_operation("Violated Keep", "Violated Drop", "identical")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "identical membership" in plan.plan_refused[0].reason

            consolidate_groups.run(session)

        assert session.get(Group, drop_id) is not None

        _delete_groups(session, drop, keep)
        session.delete(session.get(Thing, shared.id))
        session.delete(session.get(Thing, stray.id))
        session.commit()


def test_prepass_refuses_when_row_to_delete_has_children():
    with session_ctx() as session:
        keep = Group(name="Parent Keep", group_type="Monitoring Plan")
        drop = Group(name="Parent Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        child = Group(
            name="Parent Drop Child",
            group_type="Monitoring Plan",
            parent_group_id=drop.id,
        )
        session.add(child)
        session.commit()
        session.refresh(child)

        with _operations(_operation("Parent Keep", "Parent Drop", "disjoint")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "child group" in plan.plan_refused[0].reason

            consolidate_groups.run(session)

        assert session.get(Group, child.id) is not None

        _delete_groups(session, child, drop, keep)


def test_prepass_refuses_when_row_to_delete_holds_a_boundary():
    with session_ctx() as session:
        keep = Group(name="Boundary Keep", group_type="Monitoring Plan")
        drop = Group(
            name="Boundary Drop", group_type="Monitoring Plan", project_area=AREA_B
        )
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        with _operations(_operation("Boundary Keep", "Boundary Drop", "disjoint")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "project_area" in plan.plan_refused[0].reason

            consolidate_groups.run(session)

        assert session.get(Group, drop.id) is not None

        _delete_groups(session, drop, keep)


def test_prepass_refuses_when_the_named_rows_are_absent():
    """Guards the production table against ever acting on an unrelated database."""
    with session_ctx() as session:
        with _operations(_operation("Absent Keep", "Absent Drop", "identical")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "expected exactly one group" in plan.plan_refused[0].reason


def test_prepass_is_idempotent():
    with session_ctx() as session:
        keep = Group(name="Twice Keep", group_type="Monitoring Plan")
        drop = Group(name="Twice Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        operation = _operation("Twice Keep", "Twice Drop", "disjoint", "Twice Renamed")
        with _operations(operation):
            consolidate_groups.run(session)
            consolidate_groups.run(session)

            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_already_applied) == 1
            assert plan.plan_merges == []

        session.refresh(keep)
        assert keep.name == "Twice Renamed"

        _delete_groups(session, keep)


def test_duplicate_plan_operations_table_is_internally_consistent():
    survivors = set()
    deletions = set()
    for operation in consolidate_groups.DUPLICATE_PLAN_OPERATIONS:
        assert operation.membership in consolidate_groups._MEMBERSHIP_RULES
        # 'none' skips the membership comparison, so it must not be paired with
        # a deletion or the operation would merge unchecked.
        if operation.membership == "none":
            assert operation.delete_name is None
        assert operation.keep_name != operation.delete_name
        assert operation.rename_to is None or operation.rename_to
        assert operation.note
        survivors.add(operation.keep_name)
        if operation.delete_name:
            deletions.add(operation.delete_name)
    assert not survivors & deletions


def test_manual_matches_do_not_reference_a_renamed_group():
    """A stale target fails soft: the boundary quietly never lands."""
    renamed = {
        operation.keep_name
        for operation in consolidate_groups.DUPLICATE_PLAN_OPERATIONS
        if operation.rename_to
    }
    assert not renamed & set(consolidate_groups.MANUAL_MATCHES.values())


def test_prepass_refuses_membership_none_paired_with_a_deletion():
    """'none' skips the comparison, so it must never guard a real merge."""
    with session_ctx() as session:
        keep = Group(name="Mislabelled Keep", group_type="Monitoring Plan")
        drop = Group(name="Mislabelled Drop", group_type="Monitoring Plan")
        session.add_all([keep, drop])
        session.commit()
        session.refresh(keep)
        session.refresh(drop)

        with _operations(_operation("Mislabelled Keep", "Mislabelled Drop", "none")):
            plan = consolidate_groups.resolve_plan_operations(session)
            assert len(plan.plan_refused) == 1
            assert "rename-only" in plan.plan_refused[0].reason

            consolidate_groups.run(session)

        assert session.get(Group, drop.id) is not None

        _delete_groups(session, drop, keep)
