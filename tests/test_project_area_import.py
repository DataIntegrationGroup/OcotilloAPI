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
"""
Database-backed tests for the OBJECTID-driven project area importer.

The fake session in tests/test_cli_commands.py cannot express "this name is
owned by two rows" or the create path, which are the two behaviours that stop
the importer reintroducing the duplicates the consolidation removes, so those
are covered here against a real database.
"""

from contextlib import contextmanager

from sqlalchemy import select

from cli import project_area_import as importer
from db.engine import session_ctx
from db.group import Group

POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-107.2, 33.6],
            [-106.6, 33.6],
            [-106.6, 34.2],
            [-107.2, 34.2],
            [-107.2, 33.6],
        ]
    ],
}
OTHER_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-105.2, 32.6],
            [-104.6, 32.6],
            [-104.6, 33.2],
            [-105.2, 33.2],
            [-105.2, 32.6],
        ]
    ],
}
POLYGON_WKT = importer._geojson_to_multipolygon_wkt(POLYGON)


@contextmanager
def _mappings(table):
    original = importer.PROJECT_AREA_MAPPINGS
    importer.PROJECT_AREA_MAPPINGS = table
    try:
        yield
    finally:
        importer.PROJECT_AREA_MAPPINGS = original


def _feature(object_id, location, geometry=None):
    return {
        "properties": {"OBJECTID": object_id, "location": location},
        "geometry": geometry or POLYGON,
    }


def _delete_groups(session, *groups):
    for group in groups:
        existing = session.get(Group, group.id) if group.id is not None else None
        if existing is not None:
            session.delete(existing)
    session.commit()


def test_plan_matches_group_regardless_of_group_type():
    """The owner of a boundary is usually a Monitoring Plan after consolidation."""
    with session_ctx() as session:
        plan_group = Group(name="Import Plan Owner", group_type="Monitoring Plan")
        session.add(plan_group)
        session.commit()
        session.refresh(plan_group)

        with _mappings({7: importer.ProjectAreaMapping("Import Plan Owner")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Some Study Area")]
            )

        assert [action.action for action in actions] == [importer.UPDATE]
        assert actions[0].group_id == plan_group.id

        importer._apply_area_action(session, actions[0])
        session.commit()
        session.refresh(plan_group)
        assert plan_group.project_area is not None
        assert plan_group.group_type == "Monitoring Plan"

        _delete_groups(session, plan_group)


def test_plan_publishes_a_draft_group_that_gains_a_boundary():
    with session_ctx() as session:
        plan_group = Group(name="Import Draft Owner", group_type="Monitoring Plan")
        session.add(plan_group)
        session.commit()
        session.refresh(plan_group)
        assert plan_group.release_status == "draft"

        with _mappings({7: importer.ProjectAreaMapping("Import Draft Owner")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Some Study Area")]
            )

        assert actions[0].publishes is True
        importer._apply_area_action(session, actions[0])
        session.commit()
        session.refresh(plan_group)
        assert plan_group.release_status == "public"

        _delete_groups(session, plan_group)


def test_plan_refuses_name_owned_by_two_groups():
    """Updating every match is how the old importer clobbered boundaries."""
    with session_ctx() as session:
        area = Group(name="Import Twin", group_type="Geographic Area")
        plan_group = Group(name="Import Twin", group_type="Monitoring Plan")
        session.add_all([area, plan_group])
        session.commit()
        session.refresh(area)
        session.refresh(plan_group)

        with _mappings({7: importer.ProjectAreaMapping("Import Twin")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Import Twin")]
            )

        assert actions[0].action == importer.SKIP
        assert "owned by 2 groups" in actions[0].reason

        importer._apply_area_action(session, actions[0])
        session.commit()
        for group in (area, plan_group):
            session.refresh(group)
            assert group.project_area is None

        _delete_groups(session, area, plan_group)


def test_plan_creates_missing_mapped_area_as_public():
    with session_ctx() as session:
        table = {
            7: importer.ProjectAreaMapping("Import Brand New", create_if_missing=True)
        }
        with _mappings(table):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Import Brand New")]
            )

        assert actions[0].action == importer.CREATE
        importer._apply_area_action(session, actions[0])
        session.commit()

        created = session.scalars(
            select(Group).where(Group.name == "Import Brand New")
        ).one()
        assert created.group_type == "Geographic Area"
        assert created.release_status == "public"
        assert created.project_area is not None

        _delete_groups(session, created)


def test_plan_skips_a_missing_name_it_is_not_allowed_to_create():
    """The guard that stops a re-import resurrecting a consolidated area."""
    with session_ctx() as session:
        with _mappings({7: importer.ProjectAreaMapping("Import Never Created")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Import Never Created")]
            )

        assert actions[0].action == importer.SKIP
        assert "not allowed to create it" in actions[0].reason
        assert (
            session.scalars(
                select(Group).where(Group.name == "Import Never Created")
            ).all()
            == []
        )


def test_plan_skips_an_unmapped_objectid():
    with session_ctx() as session:
        with _mappings({}):
            actions = importer.plan_project_area_import(
                session, [_feature(999, "Import Unmapped")]
            )

        assert actions[0].action == importer.SKIP
        assert "not in PROJECT_AREA_MAPPINGS" in actions[0].reason


def test_plan_reports_unchanged_geometry_without_rewriting():
    with session_ctx() as session:
        area = Group(
            name="Import Steady",
            group_type="Geographic Area",
            project_area=POLYGON_WKT,
            release_status="public",
        )
        session.add(area)
        session.commit()
        session.refresh(area)

        with _mappings({7: importer.ProjectAreaMapping("Import Steady")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Import Steady")]
            )

        assert actions[0].action == importer.UNCHANGED
        assert actions[0].wkt is None

        _delete_groups(session, area)


def test_import_is_idempotent():
    with session_ctx() as session:
        table = {
            7: importer.ProjectAreaMapping("Import Repeatable", create_if_missing=True)
        }
        with _mappings(table):
            first = importer.plan_project_area_import(
                session, [_feature(7, "Import Repeatable")]
            )
            importer._apply_area_action(session, first[0])
            session.commit()

            second = importer.plan_project_area_import(
                session, [_feature(7, "Import Repeatable")]
            )

        assert first[0].action == importer.CREATE
        assert second[0].action == importer.UNCHANGED

        created = session.scalars(
            select(Group).where(Group.name == "Import Repeatable")
        ).one()
        _delete_groups(session, created)


def test_changed_upstream_geometry_is_rewritten():
    with session_ctx() as session:
        area = Group(
            name="Import Moved",
            group_type="Geographic Area",
            project_area=POLYGON_WKT,
            release_status="public",
        )
        session.add(area)
        session.commit()
        session.refresh(area)

        with _mappings({7: importer.ProjectAreaMapping("Import Moved")}):
            actions = importer.plan_project_area_import(
                session, [_feature(7, "Import Moved", geometry=OTHER_POLYGON)]
            )

        assert actions[0].action == importer.UPDATE
        assert actions[0].wkt is not None
        assert actions[0].publishes is False

        _delete_groups(session, area)


def test_plan_refuses_a_second_entry_claiming_the_same_name():
    """Every lookup reads pre-run state, so the collision is caught here."""
    with session_ctx() as session:
        table = {
            7: importer.ProjectAreaMapping("Import Contested", create_if_missing=True),
            8: importer.ProjectAreaMapping("import contested ", create_if_missing=True),
        }
        with _mappings(table):
            actions = importer.plan_project_area_import(
                session,
                [_feature(7, "First"), _feature(8, "Second")],
            )

        assert [action.action for action in actions] == [importer.CREATE, importer.SKIP]
        assert "already claimed" in actions[1].reason
        assert (
            session.scalars(
                select(Group).where(Group.name.ilike("import contested%"))
            ).all()
            == []
        )


def test_every_mapping_entry_is_unique_after_normalization():
    """
    Uniqueness has to use the lookup's key, not the raw string.

    uq_group_name_type is on the raw column and Postgres equality is
    case-sensitive, so 'Water Level Network' and 'water Level Network' coexist
    today. A raw-string assertion reads that pair as unique; the importer's
    lower+trim lookup reads it as one group.
    """
    mappings = importer.PROJECT_AREA_MAPPINGS.values()
    names = [mapping.group_name for mapping in mappings]
    assert all(name and name.strip() == name for name in names)
    normalized = [importer._normalize_name(name) for name in names]
    assert len(set(normalized)) == len(normalized)
