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
import csv
import uuid
import importlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy_continuum import version_class

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
    "data_migrations.migrations._superseded."
    "20260810_0001_consolidate_geographic_area_groups"
)
convert_casing_diameter = importlib.import_module(
    "data_migrations.migrations." "20260914_0001_convert_well_inventory_casing_diameter"
)
backfill_thing_release_status = importlib.import_module(
    "data_migrations.migrations."
    "20261001_0001_backfill_well_inventory_thing_release_status"
)
backfill_water_level_release_status = importlib.import_module(
    "data_migrations.migrations."
    "20261110_0001_backfill_imported_water_level_release_status"
)
parity_groups = importlib.import_module(
    "data_migrations.migrations." "20260905_0003_group_table_parity_with_staging"
)
seed_epa_limits = importlib.import_module(
    "data_migrations.migrations.20260916_0001_seed_epa_regulatory_limits"
)
olwc_corrections = importlib.import_module(
    "data_migrations.migrations." "20261002_0001_correct_olwc_well_depth_and_mp_height"
)
backfill_stratigraphic_intervals = importlib.import_module(
    "data_migrations.migrations." "20261105_0001_backfill_stratigraphic_intervals"
)
from db.geologic_formation import GeologicFormation
from db.lexicon import LexiconCategory
from db.ngwmn_views import NGWMNLithology
from db.nma_legacy import NMA_Stratigraphy
from db.location import Location, LocationThingAssociation
from db.notes import Notes
from db.parameter import Parameter
from db.regulatory_limit import RegulatoryLimit
from db.field import FieldActivity, FieldEvent
from db.group import Group, GroupThingAssociation
from db.measuring_point_history import MeasuringPointHistory
from db.observation import Observation
from db.sample import Sample
from db.thing import Thing
from db.stratigraphic_interval import StratigraphicInterval
from db.engine import session_ctx
from db.transducer import TransducerObservation
import services.water_level_csv as water_level_csv
from services.water_level_csv import bulk_upload_water_levels
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


def _epa_limits(session):
    return {
        (name, matrix, limit_type): float(value)
        for name, matrix, limit_type, value in session.execute(
            select(
                Parameter.parameter_name,
                Parameter.matrix,
                RegulatoryLimit.limit_type,
                RegulatoryLimit.limit_value,
            )
            .join(Parameter)
            .where(RegulatoryLimit.limit_source == "EPA")
        )
    }


def test_seed_epa_regulatory_limits_matches_seed_file():
    """conftest seeds the limits; the migration and the seed agree."""
    expected = {
        (row["parameter_name"], row["matrix"], row["limit_type"]): row["limit_value"]
        for row in seed_epa_limits.load_regulatory_limits()
    }
    with session_ctx() as session:
        seed_epa_limits.run(session)
        session.commit()
        assert _epa_limits(session) == expected


def test_seed_epa_regulatory_limits_restores_missing_and_keeps_edits():
    key = ("Arsenic", "groundwater", "MCL")
    with session_ctx() as session:
        arsenic_id = session.scalar(
            select(Parameter.id).where(
                Parameter.parameter_name == "Arsenic",
                Parameter.matrix == "groundwater",
            )
        )
        fluoride_mcl = (
            select(RegulatoryLimit)
            .join(Parameter)
            .where(
                Parameter.parameter_name == "Fluoride",
                RegulatoryLimit.limit_source == "EPA",
                RegulatoryLimit.limit_type == "MCL",
            )
        )
        session.scalar(fluoride_mcl).limit_value = 99
        session.execute(
            delete(RegulatoryLimit).where(
                RegulatoryLimit.parameter_id == arsenic_id,
                RegulatoryLimit.limit_source == "EPA",
                RegulatoryLimit.limit_type == "MCL",
            )
        )
        session.commit()

        try:
            seed_epa_limits.run(session)
            session.commit()
            limits = _epa_limits(session)
            assert limits[key] == 0.01
            assert limits[("Fluoride", "groundwater", "MCL")] == 99

            before = len(limits)
            seed_epa_limits.run(session)
            session.commit()
            assert len(_epa_limits(session)) == before
        finally:
            session.scalar(fluoride_mcl).limit_value = 4.0
            session.commit()


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


# ==============================================================================
# BDMS-1143: webmap removals
# ==============================================================================


@contextmanager
def _webmap(origin=(), stale=(), owners=()):
    """
    Point the removal pass at this test's rows only.

    PROJECT_AREA_MAPPINGS is patched on the migration module, not on
    cli.project_area_import, because the `from ... import` binding was made at
    import time and does not follow the source module.
    """
    from cli.project_area_import import ProjectAreaMapping

    saved = (
        consolidate_groups.WEBMAP_ORIGIN_NAMES,
        consolidate_groups.STALE_BOUNDARY_NAMES,
        consolidate_groups.PROJECT_AREA_MAPPINGS,
    )
    consolidate_groups.WEBMAP_ORIGIN_NAMES = frozenset(origin)
    consolidate_groups.STALE_BOUNDARY_NAMES = frozenset(stale)
    consolidate_groups.PROJECT_AREA_MAPPINGS = {
        index: ProjectAreaMapping(name) for index, name in enumerate(owners, start=1)
    }
    try:
        yield
    finally:
        (
            consolidate_groups.WEBMAP_ORIGIN_NAMES,
            consolidate_groups.STALE_BOUNDARY_NAMES,
            consolidate_groups.PROJECT_AREA_MAPPINGS,
        ) = saved


def test_removal_deletes_a_webmap_area_the_layer_no_longer_has():
    with session_ctx() as session:
        area = Group(
            name="Removal Gone Area",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add(area)
        session.commit()
        session.refresh(area)

        well = _make_thing(session, "Removal Gone Well")
        _link(session, area, well)
        area_id = area.id

        with _webmap(origin={"Removal Gone Area"}):
            consolidate_groups.run(session)

        assert session.get(Group, area_id) is None
        # The wells outlive the group. thing has no FK to group, so the cascade
        # can only reach the association rows.
        assert session.get(Thing, well.id) is not None
        assert _linked_thing_ids(session, area_id) == set()

        session.delete(session.get(Thing, well.id))
        session.commit()


def test_removal_strips_a_legacy_boundary_and_leaves_the_row():
    with session_ctx() as session:
        legacy = Group(
            name="Removal Legacy Project",
            group_type="Monitoring Plan",
            project_area=AREA_A,
            release_status="public",
        )
        session.add(legacy)
        session.commit()
        session.refresh(legacy)

        well = _make_thing(session, "Removal Legacy Well")
        _link(session, legacy, well)

        with _webmap(stale={"Removal Legacy Project"}):
            consolidate_groups.run(session)

        session.refresh(legacy)
        assert legacy.project_area is None
        assert legacy.release_status == "draft"
        assert _linked_thing_ids(session, legacy.id) == {well.id}

        _delete_groups(session, legacy)
        session.delete(session.get(Thing, well.id))
        session.commit()


def test_removal_leaves_a_group_that_still_owns_a_live_feature():
    with session_ctx() as session:
        kept = Group(
            name="Removal Live Area",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add(kept)
        session.commit()
        session.refresh(kept)

        with _webmap(origin={"Removal Live Area"}, owners={"Removal Live Area"}):
            plan = consolidate_groups.dry_run(session)
            assert [s for s in plan.removals if s.group_id == kept.id] == []
            consolidate_groups.run(session)

        session.refresh(kept)
        assert kept.project_area is not None
        assert kept.release_status == "public"

        _delete_groups(session, kept)


def test_removal_runs_after_the_merge_so_the_boundary_is_donated_first():
    """
    The ordering the whole design turns on.

    The area is webmap-origin and owns no feature, so a removal pass that ran first
    would delete it and destroy the polygon. Running last, it finds the area
    already merged away and the polygon on the project record.
    """
    with session_ctx() as session:
        target = Group(name="Removal Order Target", group_type="Monitoring Plan")
        area = Group(
            name="Removal Order Area",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add_all([target, area])
        session.commit()
        session.refresh(target)
        session.refresh(area)
        area_id = area.id

        consolidate_groups.MANUAL_MATCHES["Removal Order Area"] = "Removal Order Target"
        try:
            with _webmap(
                origin={"Removal Order Area"}, owners={"Removal Order Target"}
            ):
                consolidate_groups.run(session)
        finally:
            consolidate_groups.MANUAL_MATCHES.pop("Removal Order Area", None)

        assert session.get(Group, area_id) is None
        session.refresh(target)
        assert target.project_area is not None
        assert target.release_status == "public"

        _delete_groups(session, target)


def test_removal_refuses_to_delete_a_group_with_children():
    with session_ctx() as session:
        parent = Group(
            name="Removal Parent Area",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        session.add(parent)
        session.commit()
        session.refresh(parent)

        child = Group(
            name="Removal Parent Child",
            group_type="Monitoring Plan",
            parent_group_id=parent.id,
        )
        session.add(child)
        session.commit()
        session.refresh(child)

        with _webmap(origin={"Removal Parent Area"}):
            plan = consolidate_groups.dry_run(session)
            refusals = [r for r in plan.removals_refused if r.group_id == parent.id]
            assert len(refusals) == 1
            assert "child group" in refusals[0].reason

            consolidate_groups.run(session)

        assert session.get(Group, parent.id) is not None
        assert session.get(Group, child.id) is not None

        _delete_groups(session, child, parent)


def test_removal_is_idempotent():
    with session_ctx() as session:
        legacy = Group(
            name="Removal Twice Project",
            group_type="Monitoring Plan",
            project_area=AREA_A,
            release_status="public",
        )
        session.add(legacy)
        session.commit()
        session.refresh(legacy)

        with _webmap(stale={"Removal Twice Project"}):
            consolidate_groups.run(session)
            consolidate_groups.run(session)

            plan = consolidate_groups.dry_run(session)
            assert [s for s in plan.removals if s.group_id == legacy.id] == []

        session.refresh(legacy)
        assert legacy.project_area is None
        assert legacy.release_status == "draft"

        _delete_groups(session, legacy)


def test_removal_dry_run_reports_both_actions_without_writing():
    with session_ctx() as session:
        area = Group(
            name="Removal Preview Area",
            group_type="Geographic Area",
            project_area=AREA_A,
            release_status="public",
        )
        legacy = Group(
            name="Removal Preview Project",
            group_type="Monitoring Plan",
            project_area=AREA_B,
            release_status="public",
        )
        session.add_all([area, legacy])
        session.commit()
        session.refresh(area)
        session.refresh(legacy)

        with _webmap(
            origin={"Removal Preview Area"}, stale={"Removal Preview Project"}
        ):
            plan = consolidate_groups.dry_run(session)

        actions = {s.group_name: s.action for s in plan.removals}
        assert actions == {
            "Removal Preview Area": "delete",
            "Removal Preview Project": "strip",
        }

        assert session.get(Group, area.id) is not None
        session.refresh(legacy)
        assert legacy.project_area is not None
        assert legacy.release_status == "public"

        _delete_groups(session, area, legacy)


def test_manual_matches_are_all_webmap_origin():
    """A merge donates a boundary, so its source must be a webmap area."""
    assert set(consolidate_groups.MANUAL_MATCHES) <= (
        consolidate_groups.WEBMAP_ORIGIN_NAMES
    )


def test_removal_name_lists_do_not_overlap():
    """A name cannot be both deleted and stripped."""
    assert not (
        consolidate_groups.WEBMAP_ORIGIN_NAMES & consolidate_groups.STALE_BOUNDARY_NAMES
    )


def _make_inventory_well(session, name, diameter, created_at, activity_type):
    """A well plus the field event/activity chain the importer would have made.

    created_at is set explicitly because the migration's CUTOFF is what keeps
    correctly-imported wells out of scope, and a row inserted during the test
    run would otherwise land on the wrong side of it.
    """
    thing = Thing(
        name=name,
        thing_type="water well",
        well_casing_diameter=diameter,
        release_status="public",
    )
    session.add(thing)
    session.commit()
    session.refresh(thing)

    thing.created_at = created_at
    event = FieldEvent(thing_id=thing.id, event_date=created_at)
    session.add(event)
    session.commit()
    session.refresh(event)

    activity = FieldActivity(field_event_id=event.id, activity_type=activity_type)
    session.add(activity)
    session.commit()
    return thing


def _cleanup_wells(session, things):
    for thing in things:
        session.execute(delete(Thing).where(Thing.id == thing.id))
    session.commit()


BEFORE_CUTOFF = convert_casing_diameter.CUTOFF - timedelta(days=1)
AFTER_CUTOFF = convert_casing_diameter.CUTOFF + timedelta(days=1)


def test_convert_casing_diameter_scales_importer_wells_only(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_casing_diameter, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        imported = _make_inventory_well(
            session, "Casing Imported", 0.5, BEFORE_CUTOFF, "well inventory"
        )
        # Same shape, different activity: entered through the API, already inches.
        other = _make_inventory_well(
            session, "Casing Other Activity", 6.0, BEFORE_CUTOFF, "groundwater level"
        )

        convert_casing_diameter.run(session)

        session.refresh(imported)
        session.refresh(other)
        assert imported.well_casing_diameter == 6.0
        assert other.well_casing_diameter == 6.0

        _cleanup_wells(session, [imported, other])


def test_convert_casing_diameter_leaves_wells_created_after_cutoff(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(convert_casing_diameter, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        after = _make_inventory_well(
            session, "Casing After Cutoff", 6.0, AFTER_CUTOFF, "well inventory"
        )

        convert_casing_diameter.run(session)

        session.refresh(after)
        assert after.well_casing_diameter == 6.0

        _cleanup_wells(session, [after])


def test_convert_casing_diameter_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_casing_diameter, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        imported = _make_inventory_well(
            session, "Casing Dry Run", 0.5, BEFORE_CUTOFF, "well inventory"
        )

        planned = convert_casing_diameter.dry_run(session)

        assert imported.id in {p.thing_id for p in planned}
        session.refresh(imported)
        assert imported.well_casing_diameter == 0.5

        _cleanup_wells(session, [imported])


# ==============================================================================
# Well inventory Thing release status (20261001_0001)
# ==============================================================================


def _make_inventory_thing_at_location(
    session, name, thing_status, location_status, activity_type="well inventory"
):
    """A Thing at a Location, plus the field activity the importer stamps."""
    location = Location(
        point="POINT(-106.9 34.06)", elevation=1400.0, release_status=location_status
    )
    thing = Thing(name=name, thing_type="water well", release_status=thing_status)
    session.add_all([location, thing])
    session.commit()

    session.add(LocationThingAssociation(location_id=location.id, thing_id=thing.id))
    event = FieldEvent(thing_id=thing.id, event_date=datetime.now(timezone.utc))
    session.add(event)
    session.commit()

    session.add(FieldActivity(field_event_id=event.id, activity_type=activity_type))
    session.commit()
    session.refresh(thing)
    return thing, location


def _cleanup_things_at_locations(session, pairs):
    for thing, location in pairs:
        session.execute(delete(Thing).where(Thing.id == thing.id))
        session.execute(delete(Location).where(Location.id == location.id))
    session.commit()


def test_backfill_thing_release_status_copies_public_and_private(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_thing_release_status, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        public = _make_inventory_thing_at_location(
            session, "Release Public", "draft", "public"
        )
        private = _make_inventory_thing_at_location(
            session, "Release Private", "draft", "private"
        )

        backfill_thing_release_status.run(session)

        session.refresh(public[0])
        session.refresh(private[0])
        assert public[0].release_status == "public"
        assert private[0].release_status == "private"

        _cleanup_things_at_locations(session, [public, private])


def test_backfill_thing_release_status_leaves_other_activity_types(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(backfill_thing_release_status, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        # Same shape, different provenance: not created by the importer.
        other = _make_inventory_thing_at_location(
            session, "Release Other Activity", "draft", "public", "groundwater level"
        )

        backfill_thing_release_status.run(session)

        session.refresh(other[0])
        assert other[0].release_status == "draft"

        _cleanup_things_at_locations(session, [other])


def test_backfill_thing_release_status_keeps_non_draft_things(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_thing_release_status, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        # Someone already chose a status for this Thing; the Location must not
        # override it.
        chosen = _make_inventory_thing_at_location(
            session, "Release Already Private", "private", "public"
        )

        backfill_thing_release_status.run(session)

        session.refresh(chosen[0])
        assert chosen[0].release_status == "private"

        _cleanup_things_at_locations(session, [chosen])


def test_backfill_thing_release_status_leaves_draft_locations(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_thing_release_status, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        unanswered = _make_inventory_thing_at_location(
            session, "Release Unanswered", "draft", "draft"
        )

        planned = backfill_thing_release_status.dry_run(session)
        backfill_thing_release_status.run(session)

        assert unanswered[0].id not in {p.thing_id for p in planned}
        session.refresh(unanswered[0])
        assert unanswered[0].release_status == "draft"

        _cleanup_things_at_locations(session, [unanswered])


def test_backfill_thing_release_status_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_thing_release_status, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        imported = _make_inventory_thing_at_location(
            session, "Release Dry Run", "draft", "public"
        )

        planned = backfill_thing_release_status.dry_run(session)

        assert imported[0].id in {p.thing_id for p in planned}
        session.refresh(imported[0])
        assert imported[0].release_status == "draft"
        assert list(tmp_path.glob("backfill_thing_release_status_*.csv"))

        _cleanup_things_at_locations(session, [imported])


# ==============================================================================
# Imported water level reading release status (20261110_0001)
# ==============================================================================


@dataclass
class _ImportedReading:
    thing: Thing
    location: Location | None
    observation: Observation


def _add_reading(
    session,
    thing,
    *,
    sample_name=None,
    well_inventory=True,
    observation_status="draft",
    nma_pk_waterlevels=None,
    activity_type="groundwater level",
    measured_at=None,
):
    """A groundwater level reading on thing, shaped like an importer's.

    well_inventory adds the 'well inventory' activity that importer stamps on
    the same field event; without it the reading looks like a water level CSV
    import. sample_name None gives the importers' "<well>-WL-<YYYYMMDDHHMM>".
    """
    measured_at = measured_at or datetime.now(timezone.utc)
    event = FieldEvent(thing_id=thing.id, event_date=measured_at)
    session.add(event)
    session.commit()

    if well_inventory:
        session.add(
            FieldActivity(field_event_id=event.id, activity_type="well inventory")
        )
    activity = FieldActivity(field_event_id=event.id, activity_type=activity_type)
    session.add(activity)
    session.commit()

    sample = Sample(
        field_activity_id=activity.id,
        sample_date=measured_at,
        sample_name=sample_name or f"{thing.name}-WL-{measured_at:%Y%m%d%H%M}",
        sample_matrix="water",
        sample_method="Steel-tape measurement",
    )
    session.add(sample)
    session.commit()

    # The importers never set release_status, so a draft reading here relies
    # on the column default too; that is what Continuum's first version row
    # records, and what the history check reads.
    status = (
        {} if observation_status == "draft" else {"release_status": observation_status}
    )
    observation = Observation(
        sample_id=sample.id,
        parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
        observation_datetime=measured_at,
        value=10.0,
        unit="ft",
        nma_pk_waterlevels=nma_pk_waterlevels,
        **status,
    )
    session.add(observation)
    session.commit()
    return observation


def _add_inventory_event(session, thing):
    """A well inventory visit that recorded no water level."""
    event = FieldEvent(thing_id=thing.id, event_date=datetime.now(timezone.utc))
    session.add(event)
    session.commit()
    session.add(FieldActivity(field_event_id=event.id, activity_type="well inventory"))
    session.commit()


def _make_imported_reading(
    session,
    well_name,
    well_status,
    *,
    location_status=None,
    with_location=True,
    thing_type="water well",
    **reading,
):
    """A well, its current Location, and one reading from _add_reading."""
    thing = Thing(name=well_name, thing_type=thing_type, release_status=well_status)
    location = None
    if with_location:
        location = Location(
            point="POINT(-106.9 34.06)",
            elevation=1400.0,
            release_status=location_status or well_status,
        )
        session.add(location)
    session.add(thing)
    session.commit()

    if location is not None:
        session.add(
            LocationThingAssociation(location_id=location.id, thing_id=thing.id)
        )
        session.commit()

    observation = _add_reading(session, thing, **reading)
    session.refresh(thing)
    return _ImportedReading(thing, location, observation)


def _cleanup_imported_readings(session, readings):
    # Deleting the Thing cascades through field event, activity, sample and
    # observation; the Location has no cascade from the Thing.
    session.rollback()
    for reading in readings:
        session.execute(delete(Thing).where(Thing.id == reading.thing.id))
        if reading.location is not None:
            session.execute(delete(Location).where(Location.id == reading.location.id))
    session.commit()


def _status_of(session, observation):
    return session.scalar(
        select(Observation.release_status).where(Observation.id == observation.id)
    )


def _reading_status(session, reading):
    return _status_of(session, reading.observation)


def _plan_of(planned, observation):
    matches = [p for p in planned if p.observation_id == observation.id]
    return matches[0] if matches else None


def _planned_for(planned, reading):
    return _plan_of(planned, reading.observation)


def _observation_versions(session, observation):
    ObservationVersion = version_class(Observation)
    return session.scalars(
        select(ObservationVersion.release_status)
        .where(ObservationVersion.id == observation.id)
        .order_by(ObservationVersion.transaction_id.asc())
    ).all()


@pytest.fixture
def water_level_release_status(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_water_level_release_status, "REPORT_DIR", tmp_path)
    return backfill_water_level_release_status


def test_water_level_release_status_copies_well_inventory_well_status(
    water_level_release_status,
):
    with session_ctx() as session:
        public = _make_imported_reading(session, "WLRS Inventory Public", "public")
        private = _make_imported_reading(session, "WLRS Inventory Private", "private")
        unanswered = _make_imported_reading(session, "WLRS Inventory Draft", "draft")
        readings = [public, private, unanswered]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            assert _reading_status(session, public) == "public"
            assert _reading_status(session, private) == "private"
            assert _reading_status(session, unanswered) == "draft"
            assert {_planned_for(planned, r).source for r in readings} == {
                "well_inventory"
            }
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_copies_csv_well_status(
    water_level_release_status,
):
    with session_ctx() as session:
        current = _make_imported_reading(
            session, "WLRS CSV Current", "public", well_inventory=False
        )
        legacy_name = _make_imported_reading(
            session,
            "WLRS CSV UUID",
            "public",
            sample_name=f"wl-{uuid.uuid4()}",
            well_inventory=False,
        )
        on_private = _make_imported_reading(
            session, "WLRS CSV Private", "private", well_inventory=False
        )
        on_draft = _make_imported_reading(
            session, "WLRS CSV Draft", "draft", well_inventory=False
        )
        readings = [current, legacy_name, on_private, on_draft]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            assert _reading_status(session, current) == "public"
            assert _reading_status(session, legacy_name) == "public"
            # Same rule as well inventory: a private well's readings go
            # private, and only a draft well leaves them at draft.
            assert _reading_status(session, on_private) == "private"
            assert _reading_status(session, on_draft) == "draft"
            assert _planned_for(planned, on_draft).action == "skip_well_not_released"
            assert {_planned_for(planned, r).source for r in readings} == {
                "water_level_csv"
            }
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_publishes_a_real_csv_import(
    water_level_release_status, water_well_thing, monkeypatch
):
    """End to end through the importer, so the footprint is the real one."""
    # The importer now copies the well's status itself (BDMS-1560). The
    # backfill is for observations imported before that, which were left
    # draft, so make the importer behave as it did then. Patching the status
    # keeps the draft in observation_version too, which the backfill's history
    # check reads.
    monkeypatch.setattr(
        water_level_csv, "observation_release_status", lambda _status: "draft"
    )
    header = (
        "field_staff,well_name_point_id,field_event_date_time,"
        "measurement_date_time,sampler,sample_method,mp_height,level_status,"
        "depth_to_water_ft,data_quality,water_level_notes"
    )
    row = (
        f"A Lopez,{water_well_thing.name},2025-02-15T08:00:00-07:00,"
        "2025-02-15T10:30:00-07:00,A Lopez,electric tape,1.5,"
        "Water level not affected,7.0,"
        "Water level accurate to within two hundreths of a foot,Backfill test"
    )
    result = bulk_upload_water_levels(f"{header}\n{row}".encode("utf-8"))
    assert result.exit_code == 0, result.payload
    observation_id = result.payload["water_levels"][0]["observation_id"]

    with session_ctx() as session:
        observation = session.get(Observation, observation_id)
        assert observation.release_status == "draft"

        planned = water_level_release_status.dry_run(session)
        water_level_release_status.run(session)
        session.commit()

        plan = _plan_of(planned, observation)
        assert (plan.source, plan.action, plan.history_missing) == (
            "water_level_csv",
            "change",
            False,
        )
        assert _status_of(session, observation) == "public"
        assert _observation_versions(session, observation)[-1] == "public"


def test_water_level_release_status_leaves_released_and_legacy_readings(
    water_level_release_status,
):
    with session_ctx() as session:
        already_private = _make_imported_reading(
            session, "WLRS Already Private", "public", observation_status="private"
        )
        already_public = _make_imported_reading(
            session, "WLRS Already Public", "private", observation_status="public"
        )
        legacy = _make_imported_reading(
            session,
            "WLRS NM_Aquifer",
            "public",
            nma_pk_waterlevels=str(uuid.uuid4()),
        )
        readings = [already_private, already_public, legacy]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            assert _reading_status(session, already_private) == "private"
            assert _reading_status(session, already_public) == "public"
            assert _reading_status(session, legacy) == "draft"
            assert all(_planned_for(planned, r) is None for r in readings)
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_ignores_other_thing_and_activity_types(
    water_level_release_status,
):
    with session_ctx() as session:
        spring = _make_imported_reading(
            session, "WLRS Spring", "public", thing_type="spring"
        )
        chemistry = _make_imported_reading(
            session, "WLRS Chemistry", "public", activity_type="water chemistry"
        )
        readings = [spring, chemistry]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            for reading in readings:
                assert _reading_status(session, reading) == "draft"
                assert _planned_for(planned, reading) is None
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_reports_unrecognized_readings(
    water_level_release_status, tmp_path
):
    with session_ctx() as session:
        # Neither importer's footprint, as a hand-entered reading would look.
        by_hand = _make_imported_reading(
            session,
            "WLRS By Hand",
            "public",
            sample_name=f"manual-{uuid.uuid4()}",
            well_inventory=False,
        )
        # Prefix-only matches: the whole name must be in an importer's format.
        loose_uuid = _make_imported_reading(
            session,
            "WLRS Loose UUID",
            "public",
            sample_name=f"wl-bottle-{uuid.uuid4().hex[:6]}",
            well_inventory=False,
        )
        loose_stamp = _make_imported_reading(
            session,
            "WLRS Loose Stamp",
            "public",
            sample_name=f"WLRS Loose Stamp-WL-field-{uuid.uuid4().hex[:6]}",
            well_inventory=False,
        )
        # Another well's name: the prefix must be this well's own name.
        renamed = _make_imported_reading(
            session,
            "WLRS Renamed",
            "public",
            sample_name="WLRS Old Name-WL-202501011200",
            well_inventory=False,
        )
        # A well inventory activity alone is not enough; the importer always
        # wrote the timestamped name.
        inventory_by_hand = _make_imported_reading(
            session,
            "WLRS Inventory By Hand",
            "public",
            sample_name=f"manual-{uuid.uuid4()}",
        )
        readings = [by_hand, loose_uuid, loose_stamp, renamed, inventory_by_hand]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            for reading in readings:
                assert _reading_status(session, reading) == "draft"
                plan = _planned_for(planned, reading)
                assert (plan.source, plan.action) == (
                    "unrecognized",
                    "skip_unrecognized",
                ), reading.thing.name

            reports = sorted(tmp_path.glob("backfill_water_level_release_status_*.csv"))
            with reports[-1].open() as handle:
                rows = {
                    int(row["observation_id"]): row for row in csv.DictReader(handle)
                }
            row = rows[by_hand.observation.id]
            assert row["action"] == "skip_unrecognized"
            assert row["well_name"] == "WLRS By Hand"
            assert row["sample_name"].startswith("manual-")
            assert row["mode"] == "run"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_skips_readings_set_back_to_draft(
    water_level_release_status,
):
    with session_ctx() as session:
        set_back = _make_imported_reading(session, "WLRS Set Back", "public")
        readings = [set_back]
        try:
            # Two commits, so observation_version records both statuses.
            set_back.observation.release_status = "public"
            session.commit()
            set_back.observation.release_status = "draft"
            session.commit()

            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            assert _reading_status(session, set_back) == "draft"
            plan = _planned_for(planned, set_back)
            assert plan.action == "skip_history_non_draft"
            assert plan.after == "draft"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_changes_and_flags_readings_without_history(
    water_level_release_status,
):
    ObservationVersion = version_class(Observation)
    with session_ctx() as session:
        unversioned = _make_imported_reading(session, "WLRS No History", "public")
        readings = [unversioned]
        try:
            session.execute(
                delete(ObservationVersion).where(
                    ObservationVersion.id == unversioned.observation.id
                )
            )
            session.commit()

            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            plan = _planned_for(planned, unversioned)
            assert (plan.action, plan.history_missing) == ("change", True)
            assert _reading_status(session, unversioned) == "public"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_aborts_on_well_inventory_location_mismatch(
    water_level_release_status,
):
    with session_ctx() as session:
        mismatched = _make_imported_reading(
            session, "WLRS Mismatch", "public", location_status="private"
        )
        # A reading that would otherwise change, to prove the abort is total.
        bystander = _make_imported_reading(session, "WLRS Bystander", "public")
        readings = [mismatched, bystander]
        try:
            planned = water_level_release_status.dry_run(session)
            plan = _planned_for(planned, mismatched)
            assert plan.action == "abort_status_mismatch"
            assert (plan.before, plan.after) == ("draft", "draft")
            assert plan.location_release_status == "private"

            with pytest.raises(ValueError, match="WLRS Mismatch"):
                water_level_release_status.run(session)
            session.rollback()

            assert _reading_status(session, mismatched) == "draft"
            assert _reading_status(session, bystander) == "draft"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_aborts_on_inventoried_well_with_csv_readings(
    water_level_release_status,
):
    with session_ctx() as session:
        # Inventoried without a water level, then measured through the CSV
        # importer: still a well inventory well, so still checked.
        csv_after_inventory = _make_imported_reading(
            session,
            "WLRS Inventoried CSV",
            "public",
            location_status="private",
            well_inventory=False,
        )
        _add_inventory_event(session, csv_after_inventory.thing)
        readings = [csv_after_inventory]
        try:
            planned = water_level_release_status.dry_run(session)
            plan = _planned_for(planned, csv_after_inventory)
            assert (plan.source, plan.action) == (
                "water_level_csv",
                "abort_status_mismatch",
            )

            with pytest.raises(ValueError, match="WLRS Inventoried CSV"):
                water_level_release_status.run(session)
            session.rollback()

            assert _reading_status(session, csv_after_inventory) == "draft"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_aborts_on_well_without_current_location(
    water_level_release_status,
):
    with session_ctx() as session:
        homeless = _make_imported_reading(
            session, "WLRS No Location", "public", with_location=False
        )
        readings = [homeless]
        try:
            planned = water_level_release_status.dry_run(session)
            plan = _planned_for(planned, homeless)
            assert plan.action == "abort_status_mismatch"
            assert plan.location_release_status is None

            with pytest.raises(ValueError, match="WLRS No Location"):
                water_level_release_status.run(session)
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_ignores_mismatch_on_csv_and_draft_wells(
    water_level_release_status,
):
    with session_ctx() as session:
        # A never-inventoried well has no inventory answer to compare, and a
        # draft well inventory well has no reading to change.
        csv_only = _make_imported_reading(
            session,
            "WLRS CSV Mismatch",
            "public",
            location_status="private",
            well_inventory=False,
        )
        draft_inventory = _make_imported_reading(
            session, "WLRS Draft Mismatch", "draft", location_status="public"
        )
        readings = [csv_only, draft_inventory]
        try:
            water_level_release_status.run(session)
            session.commit()

            assert _reading_status(session, csv_only) == "public"
            assert _reading_status(session, draft_inventory) == "draft"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_classifies_both_sources_on_a_mixed_well(
    water_level_release_status,
):
    with session_ctx() as session:
        # A private well inventory well, later measured through the CSV
        # importer: each reading keeps its own source, and both take the
        # well's status.
        mixed = _make_imported_reading(session, "WLRS Mixed", "private")
        csv_reading = _add_reading(
            session,
            mixed.thing,
            well_inventory=False,
            measured_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        readings = [mixed]
        try:
            planned = water_level_release_status.dry_run(session)
            water_level_release_status.run(session)
            session.commit()

            assert _planned_for(planned, mixed).source == "well_inventory"
            assert _plan_of(planned, csv_reading).source == "water_level_csv"
            assert _reading_status(session, mixed) == "private"
            assert _status_of(session, csv_reading) == "private"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_batches_large_id_lists(
    water_level_release_status, monkeypatch
):
    monkeypatch.setattr(water_level_release_status, "ID_BATCH_SIZE", 1)
    with session_ctx() as session:
        readings = [
            _make_imported_reading(session, f"WLRS Batch {n}", "public")
            for n in range(3)
        ]
        set_back = _make_imported_reading(session, "WLRS Batch Set Back", "public")
        readings.append(set_back)
        try:
            set_back.observation.release_status = "public"
            session.commit()
            set_back.observation.release_status = "draft"
            session.commit()

            water_level_release_status.run(session)
            session.commit()

            assert [_reading_status(session, r) for r in readings[:3]] == ["public"] * 3
            assert _reading_status(session, set_back) == "draft"
        finally:
            _cleanup_imported_readings(session, readings)


def test_water_level_release_status_writes_an_observation_version(
    water_level_release_status,
):
    with session_ctx() as session:
        reading = _make_imported_reading(session, "WLRS Versioned", "public")
        try:
            # Created without an explicit status, as the importers do, and
            # Continuum still records the default.
            assert _observation_versions(session, reading.observation) == ["draft"]

            water_level_release_status.run(session)
            session.commit()

            assert _observation_versions(session, reading.observation) == [
                "draft",
                "public",
            ]
        finally:
            _cleanup_imported_readings(session, [reading])


def test_water_level_release_status_dry_run_writes_nothing(
    water_level_release_status, tmp_path
):
    with session_ctx() as session:
        reading = _make_imported_reading(session, "WLRS Dry Run", "public")
        try:
            planned = water_level_release_status.dry_run(session)
            session.rollback()

            assert _planned_for(planned, reading).action == "change"
            assert _reading_status(session, reading) == "draft"
            assert _observation_versions(session, reading.observation) == ["draft"]
            reports = list(tmp_path.glob("backfill_water_level_release_status_*.csv"))
            with reports[0].open() as handle:
                assert {row["mode"] for row in csv.DictReader(handle)} == {"dry_run"}
        finally:
            _cleanup_imported_readings(session, [reading])


def test_water_level_release_status_second_run_plans_no_changes(
    water_level_release_status,
):
    with session_ctx() as session:
        reading = _make_imported_reading(session, "WLRS Rerun", "public")
        try:
            water_level_release_status.run(session)
            session.commit()

            planned = water_level_release_status.dry_run(session)

            assert _reading_status(session, reading) == "public"
            assert [p for p in planned if p.action == "change"] == []
        finally:
            _cleanup_imported_readings(session, [reading])


# ==============================================================================
# Group table parity with staging (20260905_0003)
# ==============================================================================
#
# This migration is what every environment other than staging uses to reach
# staging's group table, so it is exercised here against small hand-built
# snapshots rather than the shipped 80-group one. The shipped file gets its own
# consistency checks at the end, which need no database.

PARITY_AREA = (
    "MULTIPOLYGON(((-108.4 35.6, -107.8 35.6, -107.8 36.2, -108.4 36.2, -108.4 35.6)))"
)
PARITY_OTHER_AREA = (
    "MULTIPOLYGON(((-103.4 31.6, -102.8 31.6, -102.8 32.2, -103.4 32.2, -103.4 31.6)))"
)


def _snapshot_row(
    name,
    group_type="Monitoring Plan",
    description=None,
    release_status="draft",
    wkt=None,
    parent_name=None,
):
    return {
        "name": name,
        "group_type": group_type,
        "description": description,
        "release_status": release_status,
        "wkt": wkt,
        "parent_name": parent_name,
    }


@contextmanager
def _snapshot(rows):
    """Run the parity migration against `rows` instead of the shipped file."""
    saved = parity_groups._load_snapshot
    parity_groups._load_snapshot = lambda: rows
    try:
        yield
    finally:
        parity_groups._load_snapshot = saved


def _group_by_name(session, name):
    return session.scalars(select(Group).where(Group.name == name)).first()


def test_parity_creates_a_group_the_target_does_not_have():
    with session_ctx() as session:
        rows = [
            _snapshot_row(
                "Parity New Area",
                group_type="Geographic Area",
                description="from the snapshot",
                release_status="public",
                wkt=PARITY_AREA,
            )
        ]
        with _snapshot(rows):
            parity_groups.run(session)

        created = _group_by_name(session, "Parity New Area")
        assert created is not None
        assert created.group_type == "Geographic Area"
        assert created.description == "from the snapshot"
        assert created.release_status == "public"
        assert created.project_area is not None

        _delete_groups(session, created)


def test_parity_updates_in_place_and_keeps_the_target_id():
    """Keyed by name: ids are environment-specific and must survive."""
    with session_ctx() as session:
        group = Group(
            name="Parity Drifted Area",
            group_type="Monitoring Plan",
            description="stale",
            release_status="draft",
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        original_id = group.id

        rows = [
            _snapshot_row(
                "Parity Drifted Area",
                group_type="Geographic Area",
                description="current",
                release_status="public",
                wkt=PARITY_AREA,
            )
        ]
        with _snapshot(rows):
            parity_groups.run(session)

        session.refresh(group)
        assert group.id == original_id
        assert group.group_type == "Geographic Area"
        assert group.description == "current"
        assert group.release_status == "public"
        assert group.project_area is not None

        _delete_groups(session, group)


def test_parity_reparents_by_name_and_unparents_when_the_snapshot_does():
    with session_ctx() as session:
        rows = [
            _snapshot_row("Parity Container"),
            _snapshot_row("Parity Child", parent_name="Parity Container"),
            _snapshot_row("Parity Loose"),
        ]
        with _snapshot(rows):
            parity_groups.run(session)

        container = _group_by_name(session, "Parity Container")
        child = _group_by_name(session, "Parity Child")
        loose = _group_by_name(session, "Parity Loose")
        assert child.parent_group_id == container.id
        assert loose.parent_group_id is None

        # The snapshot is also authoritative about parents it does not set:
        # a target-side parent that staging does not have is cleared.
        loose.parent_group_id = container.id
        session.commit()
        with _snapshot(rows):
            parity_groups.run(session)
        session.refresh(loose)
        assert loose.parent_group_id is None

        _delete_groups(session, child, loose, container)


def test_parity_deletes_a_reviewed_orphan_duplicate_absent_from_the_snapshot():
    orphan_name = sorted(parity_groups.ORPHAN_DUPLICATE_NAMES)[0]
    with session_ctx() as session:
        orphan = Group(
            name=orphan_name,
            group_type="Geographic Area",
            project_area=PARITY_OTHER_AREA,
            release_status="draft",
        )
        session.add(orphan)
        session.commit()
        session.refresh(orphan)
        orphan_id = orphan.id

        rows = [_snapshot_row("Parity Keeper", wkt=PARITY_AREA)]
        with _snapshot(rows):
            parity_groups.run(session)

        assert session.get(Group, orphan_id) is None
        _delete_groups(session, _group_by_name(session, "Parity Keeper"))


def test_parity_deletes_a_snapshot_absent_group_that_duplicates_a_boundary():
    """The geometry path: same polygon under a different name."""
    with session_ctx() as session:
        duplicate = Group(
            name="Parity Boundary Duplicate",
            group_type="Geographic Area",
            project_area=PARITY_AREA,
            release_status="draft",
        )
        session.add(duplicate)
        session.commit()
        session.refresh(duplicate)
        duplicate_id = duplicate.id

        rows = [_snapshot_row("Parity Boundary Owner", wkt=PARITY_AREA)]
        with _snapshot(rows):
            parity_groups.run(session)

        assert session.get(Group, duplicate_id) is None
        _delete_groups(session, _group_by_name(session, "Parity Boundary Owner"))


def test_parity_preserves_a_snapshot_absent_group_with_its_own_boundary():
    """Under-reaching is the safe direction: extras are kept, not pruned."""
    with session_ctx() as session:
        extra = Group(
            name="Parity Local Only Area",
            group_type="Geographic Area",
            project_area=PARITY_OTHER_AREA,
            release_status="public",
        )
        session.add(extra)
        session.commit()
        session.refresh(extra)

        rows = [_snapshot_row("Parity Unrelated", wkt=PARITY_AREA)]
        with _snapshot(rows):
            plan = parity_groups.dry_run(session)
            assert "Parity Local Only Area" in plan.preserve
            assert "Parity Local Only Area" not in plan.delete_safe
            parity_groups.run(session)

        session.refresh(extra)
        assert extra.project_area is not None
        assert extra.release_status == "public"

        _delete_groups(session, extra, _group_by_name(session, "Parity Unrelated"))


def test_parity_keeps_a_snapshot_absent_group_that_carries_wells():
    """group_thing_association cascades, so a deletion here would drop wells."""
    orphan_name = sorted(parity_groups.ORPHAN_DUPLICATE_NAMES)[1]
    with session_ctx() as session:
        group = Group(
            name=orphan_name,
            group_type="Geographic Area",
            project_area=PARITY_OTHER_AREA,
            release_status="draft",
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        thing = _make_thing(session, "Parity Membership Well")
        _link(session, group, thing)

        rows = [_snapshot_row("Parity Elsewhere", wkt=PARITY_AREA)]
        with _snapshot(rows):
            plan = parity_groups.dry_run(session)
            assert orphan_name in plan.delete_blocked
            parity_groups.run(session)

        assert session.get(Group, group.id) is not None
        assert (
            session.scalars(
                select(GroupThingAssociation.thing_id).where(
                    GroupThingAssociation.group_id == group.id
                )
            ).first()
            == thing.id
        )

        _delete_groups(session, group, _group_by_name(session, "Parity Elsewhere"))
        session.delete(session.get(Thing, thing.id))
        session.commit()


def test_parity_keeps_a_snapshot_absent_group_that_has_children():
    """parent_group_id cascades too."""
    orphan_name = sorted(parity_groups.ORPHAN_DUPLICATE_NAMES)[2]
    with session_ctx() as session:
        parent = Group(
            name=orphan_name,
            group_type="Geographic Area",
            project_area=PARITY_OTHER_AREA,
            release_status="draft",
        )
        session.add(parent)
        session.commit()
        session.refresh(parent)
        child = Group(
            name="Parity Surviving Child",
            group_type="Monitoring Plan",
            parent_group_id=parent.id,
        )
        session.add(child)
        session.commit()
        session.refresh(child)

        rows = [_snapshot_row("Parity Somewhere Else", wkt=PARITY_AREA)]
        with _snapshot(rows):
            plan = parity_groups.dry_run(session)
            assert orphan_name in plan.delete_blocked
            parity_groups.run(session)

        assert session.get(Group, parent.id) is not None
        session.refresh(child)
        assert child.parent_group_id == parent.id

        # Child first, in its own commit: parent_group_id cascades, so deleting
        # both in one flush lets the database remove the child out from under
        # the ORM's own DELETE for it.
        _delete_groups(session, child)
        _delete_groups(
            session, parent, _group_by_name(session, "Parity Somewhere Else")
        )


def test_parity_does_not_copy_or_remove_well_memberships():
    """Memberships are environment-specific; parity reconciles groups only."""
    with session_ctx() as session:
        group = Group(
            name="Parity Membership Holder",
            group_type="Monitoring Plan",
            release_status="draft",
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        thing = _make_thing(session, "Parity Kept Well")
        _link(session, group, thing)

        rows = [
            _snapshot_row(
                "Parity Membership Holder",
                group_type="Geographic Area",
                release_status="public",
            )
        ]
        with _snapshot(rows):
            parity_groups.run(session)

        session.refresh(group)
        assert group.release_status == "public"
        linked = session.scalars(
            select(GroupThingAssociation.thing_id).where(
                GroupThingAssociation.group_id == group.id
            )
        ).all()
        assert list(linked) == [thing.id]

        _delete_groups(session, group)
        session.delete(session.get(Thing, thing.id))
        session.commit()


def test_parity_dry_run_writes_nothing():
    with session_ctx() as session:
        existing = Group(
            name="Parity Preview Target",
            group_type="Monitoring Plan",
            description="untouched",
            release_status="draft",
        )
        session.add(existing)
        session.commit()
        session.refresh(existing)

        rows = [
            _snapshot_row(
                "Parity Preview Target",
                group_type="Geographic Area",
                description="would change",
                release_status="public",
            ),
            _snapshot_row("Parity Preview New"),
        ]
        with _snapshot(rows):
            plan = parity_groups.dry_run(session)

        assert "Parity Preview New" in plan.create
        assert "Parity Preview Target" in plan.update

        session.refresh(existing)
        assert existing.group_type == "Monitoring Plan"
        assert existing.description == "untouched"
        assert existing.release_status == "draft"
        assert _group_by_name(session, "Parity Preview New") is None

        _delete_groups(session, existing)


def test_parity_is_idempotent():
    with session_ctx() as session:
        rows = [
            _snapshot_row("Parity Idempotent Container"),
            _snapshot_row(
                "Parity Idempotent Child",
                group_type="Geographic Area",
                release_status="public",
                wkt=PARITY_AREA,
                parent_name="Parity Idempotent Container",
            ),
        ]
        with _snapshot(rows):
            parity_groups.run(session)
            plan = parity_groups.dry_run(session)

        assert plan.create == []
        assert plan.update == []
        assert plan.reparent == []
        assert sorted(plan.unchanged) == [
            "Parity Idempotent Child",
            "Parity Idempotent Container",
        ]

        _delete_groups(
            session,
            _group_by_name(session, "Parity Idempotent Child"),
            _group_by_name(session, "Parity Idempotent Container"),
        )


# --- the shipped snapshot itself; no database needed -------------------------


def test_shipped_snapshot_names_are_unique():
    rows = parity_groups._load_snapshot()
    names = [row["name"] for row in rows]
    assert len(names) == len(set(names))


def test_shipped_snapshot_parents_are_all_in_the_snapshot():
    """run() resolves parents out of the snapshot; a dangling one is a KeyError."""
    rows = parity_groups._load_snapshot()
    names = {row["name"] for row in rows}
    dangling = {
        row["parent_name"]
        for row in rows
        if row["parent_name"] is not None and row["parent_name"] not in names
    }
    assert dangling == set()


def test_shipped_snapshot_has_no_parent_cycles():
    rows = parity_groups._load_snapshot()
    parents = {row["name"]: row["parent_name"] for row in rows}
    for name in parents:
        seen = set()
        current = name
        while current is not None:
            assert current not in seen, f"parent cycle through {current}"
            seen.add(current)
            current = parents.get(current)


def test_shipped_snapshot_rows_carry_every_field_the_migration_writes():
    rows = parity_groups._load_snapshot()
    required = {"name", "group_type", "description", "release_status", "wkt"}
    for row in rows:
        assert required <= set(row), row.get("name")


def test_orphan_duplicate_names_are_absent_from_the_snapshot():
    """A name in both lists would be created and then deleted in one run."""
    rows = parity_groups._load_snapshot()
    names = {row["name"] for row in rows}
    assert not (parity_groups.ORPHAN_DUPLICATE_NAMES & names)


# --- OLWC 2025 well depth and MP height corrections ---------------------------

# The Things were created, and their placeholder history rows started, on this
# day. The migration keeps the date on the wells that need one value.
PLACEHOLDER_START = date(2026, 2, 27)


def _make_olwc_well(session, name, readings=(), history=None, depth=None):
    """A water well with water level readings (day, MP height) and MP history.

    history defaults to the single null-height placeholder row staging has.
    Each history item is (height, start_date, end_date).
    """
    thing = Thing(
        name=name,
        thing_type="water well",
        well_depth=depth,
        release_status="public",
    )
    session.add(thing)
    session.commit()
    session.refresh(thing)

    for day, mp in readings:
        moment = datetime.combine(day, time(17, 0), tzinfo=timezone.utc)
        event = FieldEvent(thing_id=thing.id, event_date=moment)
        session.add(event)
        session.commit()
        activity = FieldActivity(
            field_event_id=event.id, activity_type="groundwater level"
        )
        session.add(activity)
        session.commit()
        sample = Sample(
            field_activity_id=activity.id,
            sample_date=moment,
            sample_name=f"{name} reading {day}",
            sample_matrix="water",
            sample_method="Steel-tape measurement",
            qc_type="Normal",
        )
        session.add(sample)
        session.commit()
        session.add(
            Observation(
                sample_id=sample.id,
                parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
                observation_datetime=moment,
                value=100.0,
                unit="ft",
                measuring_point_height=mp,
            )
        )
        session.commit()

    for height, start, end in history or [(None, PLACEHOLDER_START, None)]:
        session.add(
            MeasuringPointHistory(
                thing_id=thing.id,
                measuring_point_height=height,
                start_date=start,
                end_date=end,
                release_status="public",
            )
        )
    session.commit()
    return thing


def _olwc_roster() -> set[str]:
    return (
        set(olwc_corrections.WELL_DEPTHS)
        | {fix[0] for fix in olwc_corrections.OBSERVATION_MP_FIXES}
        | set(olwc_corrections.HISTORY_SET)
        | set(olwc_corrections.HISTORY_SPLIT)
    )


def _make_olwc_roster(session, skip=()):
    """Every well the migration names, in the state staging had before it ran."""
    readings = {}
    for name, day, old, _new in olwc_corrections.OBSERVATION_MP_FIXES:
        readings.setdefault(name, []).append((day, old))
    # The latest reading of both wells already held the right value.
    readings["OG-0042"].append((date(2025, 12, 18), -0.1))
    readings["OG-0072"].append((date(2025, 12, 18), 0.0))
    return {
        name: _make_olwc_well(session, name, readings.get(name, ()))
        for name in sorted(_olwc_roster())
        if name not in skip
    }


def _olwc_history(session, thing):
    return [
        (float(r.measuring_point_height), r.start_date, r.end_date)
        for r in session.scalars(
            select(MeasuringPointHistory)
            .where(MeasuringPointHistory.thing_id == thing.id)
            .order_by(MeasuringPointHistory.start_date)
        )
    ]


def _olwc_reading_mps(session, thing):
    return [
        (o.observation_datetime.date(), o.measuring_point_height)
        for o in session.scalars(
            select(Observation)
            .join(Sample, Observation.sample_id == Sample.id)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
            .where(FieldEvent.thing_id == thing.id)
            .order_by(Observation.observation_datetime)
        )
    ]


def test_olwc_constants_are_consistent():
    mod = olwc_corrections
    assert len(mod.WELL_DEPTHS) == 6
    assert len(mod.HISTORY_SET) == 14
    assert set(mod.HISTORY_SPLIT) == {"OG-0016", "OG-0072"}
    # A well is filled in one way or the other, never both.
    assert not set(mod.HISTORY_SET) & set(mod.HISTORY_SPLIT)
    # Wells deliberately left alone.
    for untouched in ("OG-0031", "OG-0067", "OG-0092", "OG-0093", "OG-0094"):
        assert untouched not in _olwc_roster()
    # Every corrected reading gets a matching history height.
    for name, _day, _old, new in mod.OBSERVATION_MP_FIXES:
        expected = mod.HISTORY_SET.get(name)
        if expected is not None:
            assert expected == new
    for name, periods in mod.HISTORY_SPLIT.items():
        *earlier, current = periods
        assert current[2] is None, f"{name} current row must stay open"
        for (_h, _s, end), (_h2, next_start, _e2) in zip(periods, periods[1:]):
            assert end == next_start, f"{name} rows must be contiguous"
        assert all(end is not None for _h, _s, end in earlier)


def test_olwc_corrections_apply_the_decided_values(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    mod = olwc_corrections
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            mod.run(session)
            session.commit()
            session.expire_all()

            for name, depth in mod.WELL_DEPTHS.items():
                assert wells[name].well_depth == depth
            assert wells["OG-0081"].well_depth is None

            assert _olwc_reading_mps(session, wells["OG-0042"]) == [
                (date(2023, 1, 24), -0.1),
                (date(2024, 12, 18), -0.1),
                (date(2025, 12, 18), -0.1),
            ]
            assert _olwc_reading_mps(session, wells["OG-0066"]) == [
                (date(2023, 1, 24), -0.3),
                (date(2024, 12, 18), -0.3),
            ]
            assert _olwc_reading_mps(session, wells["OG-0072"]) == [
                (date(2023, 1, 25), -0.4),
                (date(2024, 12, 19), -0.4),
                (date(2025, 12, 18), 0.0),
            ]

            for name, height in mod.HISTORY_SET.items():
                assert _olwc_history(session, wells[name]) == [
                    (height, PLACEHOLDER_START, None)
                ], name
                # Numeric column: the property returns a Decimal.
                assert float(wells[name].measuring_point_height) == height

            for name, periods in mod.HISTORY_SPLIT.items():
                assert _olwc_history(session, wells[name]) == [
                    (h, s, e) for h, s, e in periods
                ], name
                # The API's value is the current row, and 0 must not read as unset.
                assert float(wells[name].measuring_point_height) == periods[-1][0]

            # Inserted rows keep the well's real status, not the model default.
            rows = session.scalars(
                select(MeasuringPointHistory).where(
                    MeasuringPointHistory.thing_id == wells["OG-0016"].id
                )
            ).all()
            assert {r.release_status for r in rows} == {"public"}
            assert len(list(tmp_path.glob("correct_olwc_*.csv"))) == 1
        finally:
            _cleanup_wells(session, list(wells.values()))


def test_olwc_corrections_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            changes = olwc_corrections.dry_run(session)
            session.rollback()
            session.expire_all()

            assert changes
            assert wells["OG-0079"].well_depth is None
            histories = session.scalars(
                select(MeasuringPointHistory).where(
                    MeasuringPointHistory.thing_id == wells["OG-0016"].id
                )
            ).all()
            assert len(histories) == 1
            assert histories[0].measuring_point_height is None
            assert len(list(tmp_path.glob("correct_olwc_*.csv"))) == 1
        finally:
            _cleanup_wells(session, list(wells.values()))


def test_olwc_corrections_second_run_finds_nothing_to_do(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            olwc_corrections.run(session)
            session.commit()

            assert olwc_corrections.dry_run(session) == []
            olwc_corrections.run(session)
            session.commit()
            session.expire_all()
            assert len(_olwc_history(session, wells["OG-0072"])) == 2
        finally:
            _cleanup_wells(session, list(wells.values()))


def _assert_olwc_run_refused(session, wells, expected_in_message):
    try:
        olwc_corrections.run(session)
    except ValueError as exc:
        assert expected_in_message in str(exc)
    else:
        raise AssertionError("expected the migration to refuse")
    session.rollback()
    session.expire_all()
    # Nothing was written, including to wells that were fine.
    assert wells["OG-0079"].well_depth is None
    assert _olwc_reading_mps(session, wells["OG-0066"])[0][1] == 0.3


def test_olwc_corrections_refuse_when_a_well_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session, skip=("OG-0027",))
        try:
            _assert_olwc_run_refused(session, wells, "OG-0027: expected 1 water well")
        finally:
            _cleanup_wells(session, list(wells.values()))


def test_olwc_corrections_refuse_a_duplicate_well_name(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        twin = _make_olwc_well(session, "OG-0027")
        try:
            _assert_olwc_run_refused(session, wells, "OG-0027: expected 1 water well")
        finally:
            _cleanup_wells(session, [*wells.values(), twin])


def test_olwc_corrections_refuse_an_unexpected_reading_value(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            reading = session.scalars(
                select(Observation)
                .join(Sample, Observation.sample_id == Sample.id)
                .where(Sample.sample_name == "OG-0072 reading 2023-01-25")
            ).one()
            reading.measuring_point_height = 0.9
            session.commit()
            _assert_olwc_run_refused(
                session, wells, "OG-0072: 2023-01-25 reading MP is 0.9"
            )
        finally:
            _cleanup_wells(session, list(wells.values()))


def test_olwc_corrections_refuse_a_depth_that_is_already_different(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            wells["OG-0086"].well_depth = 111.0
            session.commit()
            _assert_olwc_run_refused(session, wells, "OG-0086: well_depth is 111.0")
        finally:
            _cleanup_wells(session, list(wells.values()))


def test_olwc_corrections_refuse_unexpected_history(tmp_path, monkeypatch):
    monkeypatch.setattr(olwc_corrections, "REPORT_DIR", tmp_path)
    with session_ctx() as session:
        wells = _make_olwc_roster(session)
        try:
            session.add(
                MeasuringPointHistory(
                    thing_id=wells["OG-0081"].id,
                    measuring_point_height=9.0,
                    start_date=date(2026, 3, 1),
                    release_status="public",
                )
            )
            session.commit()
            _assert_olwc_run_refused(
                session, wells, "OG-0081: expected one open null-height history row"
            )
        finally:
            _cleanup_wells(session, list(wells.values()))


# --- backfill stratigraphic intervals --------------------------------------
# Real formation codes, because geologic_formation.formation_code is a foreign
# key to lexicon_term.
STRAT_MIXED = "211DKOT"  # SNDS and SDSL intervals
STRAT_KEPT = "110ALVM"  # formation lithology set; the view ignores it
STRAT_NOCODE = "310GLOR"  # intervals but no lithology code


def _strat_formations(session):
    """Get or create the test formations; return them and the ones created."""
    formations, created = {}, []
    for code in (STRAT_MIXED, STRAT_KEPT, STRAT_NOCODE):
        formation = session.scalars(
            select(GeologicFormation).where(GeologicFormation.formation_code == code)
        ).first()
        if formation is None:
            formation = GeologicFormation(formation_code=code)
            session.add(formation)
            created.append(code)
        formations[code] = formation
    session.flush()
    originals = {code: f.lithology for code, f in formations.items()}
    formations[STRAT_MIXED].lithology = None
    formations[STRAT_NOCODE].lithology = None
    formations[STRAT_KEPT].lithology = "Gravel"
    session.commit()
    return formations, created, originals


def _strat_restore(session, formations, created, originals, things):
    session.execute(
        delete(Notes).where(
            Notes.target_table == "stratigraphic_interval",
            Notes.target_id.in_(
                select(StratigraphicInterval.id).where(
                    StratigraphicInterval.thing_id.in_([t.id for t in things])
                )
            ),
        )
    )
    _cleanup_wells(session, things)
    for code, formation in formations.items():
        if code in created:
            session.delete(formation)
        else:
            formation.lithology = originals[code]
    session.commit()


def _legacy(session, thing, unit, top, bottom, code=None, guid=True, **kw):
    session.add(
        NMA_Stratigraphy(
            thing_id=thing.id,
            nma_point_id=thing.name[:10],
            nma_global_id=uuid.uuid4() if guid else None,
            unit_identifier=unit,
            strat_top=top,
            strat_bottom=bottom,
            lithology=code,
            **kw,
        )
    )


def _intervals(session, thing):
    """(formation code, top, bottom, lithology) per interval, in depth order."""
    return sorted(
        session.execute(
            select(
                GeologicFormation.formation_code,
                StratigraphicInterval.top_depth,
                StratigraphicInterval.bottom_depth,
                StratigraphicInterval.lithology,
            )
            .outerjoin(
                GeologicFormation,
                GeologicFormation.id == StratigraphicInterval.geologic_formation_id,
            )
            .where(StratigraphicInterval.thing_id == thing.id)
        ).all(),
        key=lambda r: (r[1], r[2], r[0] or "", r[3] or ""),
    )


def _interval(session, thing, top, bottom):
    return session.scalars(
        select(StratigraphicInterval).where(
            StratigraphicInterval.thing_id == thing.id,
            StratigraphicInterval.top_depth == top,
            StratigraphicInterval.bottom_depth == bottom,
        )
    ).all()


def _strat_fixture(session):
    formations, created, originals = _strat_formations(session)
    a = _make_thing(session, "STRAT-A")
    b = _make_thing(session, "STRAT-B")
    # Transferred rows: no legacy id, so the migration adopts them.
    session.add(
        StratigraphicInterval(
            thing_id=a.id,
            geologic_formation_id=formations[STRAT_MIXED].id,
            top_depth=0.0,
            bottom_depth=10.0,
        )
    )
    session.add(
        StratigraphicInterval(
            thing_id=b.id,
            geologic_formation_id=formations[STRAT_MIXED].id,
            top_depth=0.0,
            bottom_depth=5.0,
            lithology="Shale",  # set by someone: kept
        )
    )
    _legacy(
        session,
        a,
        STRAT_MIXED,
        0,
        10,
        "SNDS",
        lithologic_modifier=" red ",
        contributing_unit="Y",
        strat_source="Driller log",
        strat_notes="Cuttings only",
    )
    _legacy(session, a, " 211DKOT ", 10, 20, "snds")  # padded, lower case
    _legacy(session, a, STRAT_MIXED, 20, 30, "SDSL", contributing_unit="n")
    _legacy(session, a, STRAT_KEPT, 30, 40, "ALVM")
    _legacy(session, a, STRAT_NOCODE, 40, 50)
    _legacy(session, a, "NOTAFORMATION", 50, 60, "SHLE")  # unknown unit
    _legacy(session, a, None, 60, 70, "BSLT")  # no UnitIdentifier
    _legacy(session, a, None, 70, 80, contributing_unit="?")  # bare interval
    _legacy(session, a, STRAT_KEPT, 80, 90)  # no code: not exported
    _legacy(session, b, STRAT_MIXED, 0, 5, "SNDS")
    _legacy(session, b, STRAT_MIXED, 9, 4, "SNDS")  # top below bottom: skipped
    _legacy(session, b, STRAT_MIXED, 0, 0, "XXXX")  # both zero: kept; bad code
    _legacy(session, b, STRAT_MIXED, 5, 9, "SDSL")
    _legacy(session, b, STRAT_MIXED, 5, 9, "SNDS", guid=False)  # legacy repeat
    session.commit()
    return formations, created, originals, [a, b]


def test_backfill_stratigraphic_intervals_inserts_and_adopts():
    mod = backfill_stratigraphic_intervals
    with session_ctx() as session:
        formations, created, originals, (a, b) = _strat_fixture(session)
        try:
            mod.run(session)
            session.commit()
            session.expire_all()

            assert _intervals(session, a) == [
                (STRAT_MIXED, 0.0, 10.0, "Sandstone"),
                (STRAT_MIXED, 10.0, 20.0, "Sandstone"),
                (STRAT_MIXED, 20.0, 30.0, "Sandstone and shale"),
                (STRAT_KEPT, 30.0, 40.0, "Alluvium"),
                (STRAT_NOCODE, 40.0, 50.0, None),
                (None, 50.0, 60.0, "Shale"),
                (None, 60.0, 70.0, "Basalt"),
                (None, 70.0, 80.0, None),
                (STRAT_KEPT, 80.0, 90.0, None),
            ]
            assert _intervals(session, b) == [
                (STRAT_MIXED, 0.0, 0.0, None),
                (STRAT_MIXED, 0.0, 5.0, "Shale"),  # kept, not overwritten
                (STRAT_MIXED, 5.0, 9.0, "Sandstone"),
                (STRAT_MIXED, 5.0, 9.0, "Sandstone and shale"),
            ]

            (adopted,) = _interval(session, a, 0.0, 10.0)
            assert adopted.nma_pk_stratigraphy is not None
            assert adopted.lithologic_modifier == "red"
            assert adopted.contributing_unit is True
            assert adopted.source == "Driller log"
            assert [(n.note_type, n.content) for n in adopted.notes] == [
                ("General", "Cuttings only")
            ]
            assert _interval(session, a, 20.0, 30.0)[0].contributing_unit is False
            assert _interval(session, a, 70.0, 80.0)[0].contributing_unit is None
            assert _interval(session, b, 0.0, 5.0)[0].nma_pk_stratigraphy

            # Formation lithology is not touched.
            assert formations[STRAT_MIXED].lithology is None
            assert formations[STRAT_KEPT].lithology == "Gravel"
            assert formations[STRAT_NOCODE].lithology is None
        finally:
            _strat_restore(session, formations, created, originals, [a, b])


def test_backfill_stratigraphic_intervals_feeds_ngwmn_lithology_view():
    mod = backfill_stratigraphic_intervals
    with session_ctx() as session:
        formations, created, originals, (a, b) = _strat_fixture(session)
        try:
            mod.run(session)
            session.commit()

            rows = session.execute(
                select(
                    NGWMNLithology.strat_top,
                    NGWMNLithology.strat_bottom,
                    NGWMNLithology.lithology,
                    NGWMNLithology.term,
                    NGWMNLithology.strat_source,
                )
                .where(NGWMNLithology.point_id == a.name)
                .order_by(NGWMNLithology.strat_top)
            ).all()
            assert rows == [
                (0.0, 10.0, "Sandstone", "Sandstone", "Driller log"),
                (10.0, 20.0, "Sandstone", "Sandstone", None),
                # The interval's own code, not one value per formation.
                (20.0, 30.0, "Sandstone and shale", "Sandstone and shale", None),
                (30.0, 40.0, "Alluvium", "Alluvium", None),
                # 40-50 and 70-80 have no lithology anywhere: not exported.
                (50.0, 60.0, "Shale", "Shale", None),
                (60.0, 70.0, "Basalt", "Basalt", None),
                # 80-90 has no logged code. Its formation's lithology
                # (Gravel) is not substituted, so it is not exported.
            ]
        finally:
            _strat_restore(session, formations, created, originals, [a, b])


def test_backfill_stratigraphic_intervals_is_idempotent_and_dry_run_writes_nothing():
    mod = backfill_stratigraphic_intervals
    with session_ctx() as session:
        formations, created, originals, (a, b) = _strat_fixture(session)
        try:
            plan = mod.dry_run(session)
            session.commit()
            session.expire_all()
            assert plan["inserted"] == 11
            assert plan["updated"] == 2
            assert plan["notes"] == 1
            assert plan["stats"]["adopted"] == 2
            assert plan["stats"]["skipped_depths"] == 1
            assert plan["stats"]["inserted_without_formation"] == 3
            assert plan["unmapped_lithology"] == {"XXXX": 1}
            assert plan["unmapped_contributing_unit"] == {"?": 1}
            assert plan["unknown_units"] == {"NOTAFORMATION": 1}
            assert _intervals(session, a) == [(STRAT_MIXED, 0.0, 10.0, None)]

            mod.run(session)
            session.commit()
            first = (_intervals(session, a), _intervals(session, b))

            again = mod.dry_run(session)
            assert again["inserted"] == 0
            assert again["updated"] == 0
            mod.run(session)
            session.commit()
            session.expire_all()
            assert (_intervals(session, a), _intervals(session, b)) == first
            (adopted,) = _interval(session, a, 0.0, 10.0)
            assert len(adopted.notes) == 1
        finally:
            _strat_restore(session, formations, created, originals, [a, b])
