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
Bring a target database's ``group`` table to parity with staging's, without
replaying the consolidation and layer-18 work that produced it.

The desired end state was reached on staging by a long, one-off sequence
(consolidation, the ArcGIS layer-18 import, the parent-group migrations, and an
orphan cleanup). Reproducing that path on another database is neither
deterministic nor desirable. Instead this migration carries staging's ``group``
table as a snapshot -- ``data/20260905_0003_group_parity_snapshot.json``,
captured from ocotillo-staging -- and reconciles the target to it, keyed by
``name`` (group names are unique).

It does three things, matching only on name so it is independent of the ids each
environment assigns:

1. Upsert. Every group in the snapshot is created if absent, or updated in place
   (group_type, description, release_status, project_area) if present.
2. Re-parent. Each group's ``parent_group_id`` is set to match the snapshot,
   resolved by the parent's name. Groups unparented in the snapshot are
   unparented here too.
3. Prune, narrowly. A group present in the target but absent from the snapshot
   is deleted only when it is both safe (no ``group_thing_association`` rows and
   no child groups) and an orphan -- its boundary exactly equals a boundary that
   is in the snapshot, marking it a leftover duplicate from an earlier import.
   A snapshot-absent group with its own distinct boundary (or none) is a genuine
   target-only group and is preserved, not deleted, so parity adds staging's
   groups without removing the target's own. ``group`` has two
   ``ON DELETE CASCADE`` foreign keys (``group_thing_association.group_id`` and
   ``group.parent_group_id``), so a group carrying well memberships is never
   deleted either -- it is kept and reported. Exact parity for those is a
   separate decision, made by hand.

This reconciles the ``group`` table only. Well memberships
(``group_thing_association``) are environment-specific and are neither copied nor
removed, beyond the cascade protection above.

Gated on alembic ``d6e7f8a9b0c1`` so the project-area views exist in the target
before the groups they serve are reconciled.

Review the dry run before applying:

    oco data-migrations run 20260905_0003_group_table_parity_with_staging --dry-run
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from geoalchemy2 import WKTElement
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.group import Group
from transfers.logger import logger

SRID = 4326
SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "20260905_0003_group_parity_snapshot.json"
)

# Snapshot-absent groups that are orphan duplicates from the layer-18 import:
# each is an ArcGIS ``location``-named row whose boundary the consolidation and
# import moved onto a differently-named owner (e.g. "La Cienega Wetlands" ->
# "La Cienega"). Staging removed these; parity removes them from the target too.
# Matched by geometry when the target's copy is bit-identical to staging's, and
# by this reviewed name list otherwise -- a target's own copy can carry a drifted
# boundary that ST_Equals would miss. A name here is deleted only when it is also
# safe (no wells, no children); anything else absent from the snapshot is kept.
ORPHAN_DUPLICATE_NAMES: frozenset[str] = frozenset(
    {
        "El Camino Real and Spaceport America",
        "Española Basin and Santa Fe Area",
        "ABCWUA Groundwater Recharge",
        "Questa Area",
        "Southern Taos Valley",
        "Plains of San Agustin",
        "La Cienega Wetlands",
        "Northern Taos Plateau",
        "White Sands National Monument",
    }
)


def _load_snapshot() -> list[dict]:
    with open(SNAPSHOT_PATH) as handle:
        payload = json.load(handle)
    groups = payload["groups"]
    names = [g["name"] for g in groups]
    if len(names) != len(set(names)):
        raise ValueError("snapshot contains duplicate group names")
    return groups


@dataclass
class ParityPlan:
    create: list[str] = field(default_factory=list)
    update: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    reparent: list[str] = field(default_factory=list)
    delete_safe: list[str] = field(default_factory=list)
    delete_blocked: list[str] = field(default_factory=list)
    preserve: list[str] = field(default_factory=list)


def _geom_duplicates_snapshot(
    session: Session, group: Group, snapshot_wkts: list[str]
) -> bool:
    """True if the group's boundary exactly equals any snapshot boundary."""
    if group.project_area is None or not snapshot_wkts:
        return False
    match = or_(
        *[
            Group.project_area.ST_Equals(WKTElement(wkt, srid=SRID))
            for wkt in snapshot_wkts
        ]
    )
    return (
        session.scalar(select(Group.id).where(Group.id == group.id, match).limit(1))
        is not None
    )


def _wkt_matches(group: Group, wkt: str | None, session: Session) -> bool:
    has_geom = group.project_area is not None
    if wkt is None:
        return not has_geom
    if not has_geom:
        return False
    # Compare in the database so representations don't matter.
    return bool(
        session.scalar(
            select(Group.project_area.ST_Equals(WKTElement(wkt, srid=SRID))).where(
                Group.id == group.id
            )
        )
    )


def _by_name(session: Session) -> dict[str, Group]:
    return {g.name: g for g in session.scalars(select(Group)).all()}


def _plan(session: Session, snapshot: list[dict]) -> ParityPlan:
    plan = ParityPlan()
    existing = _by_name(session)
    id_to_name = {g.id: g.name for g in existing.values()}
    snapshot_names = {row["name"] for row in snapshot}

    for row in snapshot:
        group = existing.get(row["name"])
        if group is None:
            plan.create.append(row["name"])
            continue
        differs = (
            (group.group_type or None) != (row["group_type"] or None)
            or (group.description or None) != (row["description"] or None)
            or group.release_status != row["release_status"]
            or not _wkt_matches(group, row["wkt"], session)
        )
        (plan.update if differs else plan.unchanged).append(row["name"])
        current_parent = (
            id_to_name.get(group.parent_group_id) if group.parent_group_id else None
        )
        if current_parent != row["parent_name"]:
            plan.reparent.append(row["name"])

    snapshot_wkts = [row["wkt"] for row in snapshot if row["wkt"]]
    for name, group in existing.items():
        if name in snapshot_names:
            continue
        has_assoc = bool(group.thing_associations)
        has_children = (
            session.scalar(
                select(Group.id).where(Group.parent_group_id == group.id).limit(1)
            )
            is not None
        )
        if has_assoc or has_children:
            plan.delete_blocked.append(name)
        elif name in ORPHAN_DUPLICATE_NAMES or _geom_duplicates_snapshot(
            session, group, snapshot_wkts
        ):
            # A snapshot-absent orphan from the layer-18 import: a reviewed
            # location-named duplicate, or one whose boundary still exactly
            # equals a snapshot boundary. Safe to remove.
            plan.delete_safe.append(name)
        else:
            # Snapshot-absent, but a distinct group in its own right (its own
            # boundary or none). Preserved -- parity adds staging's groups without
            # removing a target's genuine extras.
            plan.preserve.append(name)
    return plan


def _log_plan(plan: ParityPlan) -> None:
    logger.info(
        "group parity plan: create=%d update=%d unchanged=%d reparent=%d "
        "delete_safe=%d preserve=%d delete_blocked=%d",
        len(plan.create),
        len(plan.update),
        len(plan.unchanged),
        len(plan.reparent),
        len(plan.delete_safe),
        len(plan.preserve),
        len(plan.delete_blocked),
    )
    for label, names in (
        ("create", plan.create),
        ("update", plan.update),
        ("reparent", plan.reparent),
        ("delete_safe", plan.delete_safe),
        ("preserve", plan.preserve),
        ("delete_blocked", plan.delete_blocked),
    ):
        for name in names:
            logger.info("  %-14s %s", label, name)
    if plan.preserve:
        logger.info(
            "Preserved (absent from staging, not a boundary duplicate -- kept as "
            "genuine target-only groups): %s",
            ", ".join(plan.preserve),
        )
    if plan.delete_blocked:
        logger.warning(
            "Kept (absent from staging but carry wells or children; parity for "
            "these is a manual decision): %s",
            ", ".join(plan.delete_blocked),
        )


def dry_run(session: Session) -> ParityPlan:
    plan = _plan(session, _load_snapshot())
    _log_plan(plan)
    return plan


def run(session: Session) -> None:
    snapshot = _load_snapshot()

    # Pass 1: upsert every snapshot group by name.
    existing = _by_name(session)
    for row in snapshot:
        geom = WKTElement(row["wkt"], srid=SRID) if row["wkt"] else None
        group = existing.get(row["name"])
        if group is None:
            group = Group(name=row["name"])
            session.add(group)
            existing[row["name"]] = group
        group.group_type = row["group_type"]
        group.description = row["description"]
        group.release_status = row["release_status"]
        group.project_area = geom
    session.flush()  # assign ids to newly created rows

    # Pass 2: set parent_group_id to match the snapshot, resolved by name.
    by_name = _by_name(session)
    for row in snapshot:
        group = by_name[row["name"]]
        parent_name = row["parent_name"]
        group.parent_group_id = by_name[parent_name].id if parent_name else None
    session.flush()

    # Pass 3: prune groups absent from the snapshot, safely.
    snapshot_names = {row["name"] for row in snapshot}
    plan = _plan(session, snapshot)
    for name in plan.delete_safe:
        session.delete(by_name[name])

    _log_plan(plan)
    session.commit()


MIGRATION = DataMigration(
    id="20260905_0003_group_table_parity_with_staging",
    alembic_revision="d6e7f8a9b0c1",
    name="Bring the group table to parity with staging",
    description=(
        "Reconciles the target group table to a snapshot of ocotillo-staging, "
        "keyed by name: upserts every snapshot group, re-parents to match, and "
        "deletes only snapshot-absent groups that carry no wells or children."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)
