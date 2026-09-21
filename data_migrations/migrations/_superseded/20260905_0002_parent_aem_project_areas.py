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
Group the layer-18 AEM study areas under their own parent so they get a
dedicated OGC layer separate from the general project areas.

Six features in the "Aquifer Mapping Study Areas" layer are airborne
electromagnetic (AEM) study areas. In ``cli/project_area_import.py`` they are
the owners whose name carries an "(AEM)" suffix -- each shares its upstream
``location`` with an older, non-AEM area of the same name, which is why the
importer keys on OBJECTID rather than the attribute.

This migration:

1. Creates a container group named ``AEM Project Areas``, if it does not already
   exist. It carries no boundary itself and has ``group_type`` NULL, so it never
   appears in any OGC view.
2. Re-points every AEM owner group's ``parent_group_id`` at that container.

The companion alembic migration ``d6e7f8a9b0c1`` creates
``ogc_aem_project_areas`` / ``ogc_internal_aem_project_areas`` to serve only the
container's children, and ``core/pygeoapi-config*.yml`` registers the layer.

The general study areas are handled by
``20260905_0001_parent_project_areas_under_layer18``; that migration excludes
these AEM owners, so the two parents partition the layer with no overlap.

Run order, per environment (after the general migration and the importer):

    oco import-project-area-boundaries
    oco data-migrations run 20260905_0001_parent_project_areas_under_layer18
    oco data-migrations run 20260905_0002_parent_aem_project_areas

The importer must run first: the AEM owners are ``create_if_missing`` and do not
exist until it creates them. Owners this migration cannot find are reported,
never created.

CASCADE warning: ``group.parent_group_id`` is ``ON DELETE CASCADE``. Deleting
the ``AEM Project Areas`` container would delete every AEM group with it. Do not
delete the container to "clear" the layer.

Review the dry run before applying:

    oco data-migrations run 20260905_0002_parent_aem_project_areas --dry-run
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from cli.project_area_import import PROJECT_AREA_MAPPINGS
from data_migrations.base import DataMigration
from db.group import Group
from transfers.logger import logger

PARENT_GROUP_NAME = "AEM Project Areas"
AEM_SUFFIX = "(AEM)"

# The distinct AEM owner groups (owner name carries the "(AEM)" suffix).
AEM_OWNER_NAMES: tuple[str, ...] = tuple(
    sorted(
        {
            mapping.group_name
            for mapping in PROJECT_AREA_MAPPINGS.values()
            if AEM_SUFFIX in mapping.group_name
        }
    )
)

REPARENT = "reparent"
ALREADY = "already-parented"
MISSING = "missing"


@dataclass(frozen=True)
class PlannedParentAction:
    group_name: str
    action: str
    group_id: int | None
    reason: str


def _get_parent(session: Session) -> Group | None:
    return session.scalars(select(Group).where(Group.name == PARENT_GROUP_NAME)).first()


def _plan(session: Session, parent_id: int | None) -> list[PlannedParentAction]:
    """Read-only. parent_id is None during a dry run when the parent does not
    exist yet; nothing is 'already-parented' against a parent that is absent."""
    actions: list[PlannedParentAction] = []
    for name in AEM_OWNER_NAMES:
        groups = session.scalars(select(Group).where(Group.name == name)).all()
        if not groups:
            actions.append(
                PlannedParentAction(name, MISSING, None, "no group with this name")
            )
            continue
        for group in groups:
            if group.name == PARENT_GROUP_NAME:
                continue
            if parent_id is not None and group.parent_group_id == parent_id:
                actions.append(
                    PlannedParentAction(name, ALREADY, group.id, "parent already set")
                )
            else:
                actions.append(
                    PlannedParentAction(name, REPARENT, group.id, "set parent_group_id")
                )
    return actions


def _log_actions(parent_exists: bool, actions: list[PlannedParentAction]) -> None:
    logger.info(
        "Parent group %r: %s",
        PARENT_GROUP_NAME,
        "exists" if parent_exists else "will be created",
    )
    counts: dict[str, int] = {}
    for action in actions:
        counts[action.action] = counts.get(action.action, 0) + 1
        logger.info(
            "  %-16s %-45s id=%s  %s",
            action.action,
            action.group_name,
            action.group_id,
            action.reason,
        )
    logger.info(
        "AEM owners: %d total | reparent=%d already=%d missing=%d",
        len(AEM_OWNER_NAMES),
        counts.get(REPARENT, 0),
        counts.get(ALREADY, 0),
        counts.get(MISSING, 0),
    )
    missing = [a.group_name for a in actions if a.action == MISSING]
    if missing:
        logger.warning(
            "Missing AEM owner groups (run oco import-project-area-boundaries "
            "first): %s",
            ", ".join(missing),
        )


def dry_run(session: Session) -> list[PlannedParentAction]:
    parent = _get_parent(session)
    actions = _plan(session, parent.id if parent else None)
    _log_actions(parent is not None, actions)
    return actions


def run(session: Session) -> None:
    parent = _get_parent(session)
    if parent is None:
        parent = Group(name=PARENT_GROUP_NAME, group_type=None)
        session.add(parent)
        session.flush()  # assign parent.id before re-pointing children
        logger.info("Created parent group %r (id=%s)", PARENT_GROUP_NAME, parent.id)
    else:
        logger.info(
            "Parent group %r already exists (id=%s)", PARENT_GROUP_NAME, parent.id
        )

    actions = _plan(session, parent.id)
    reparent_ids = [
        a.group_id for a in actions if a.action == REPARENT and a.group_id is not None
    ]
    if reparent_ids:
        session.execute(
            update(Group)
            .where(Group.id.in_(reparent_ids))
            .values(parent_group_id=parent.id)
        )
    _log_actions(True, actions)
    session.commit()


MIGRATION = DataMigration(
    id="20260905_0002_parent_aem_project_areas",
    alembic_revision="d6e7f8a9b0c1",
    name="Parent layer-18 AEM project areas under a container group",
    description=(
        "Creates the 'AEM Project Areas' container group and re-points every AEM "
        "layer-18 owner group (the '(AEM)' owners in PROJECT_AREA_MAPPINGS) to it, "
        "so ogc_aem_project_areas can be scoped to the container's children."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)
