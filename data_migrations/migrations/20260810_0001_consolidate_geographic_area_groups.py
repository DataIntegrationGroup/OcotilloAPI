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
BDMS-1143: merge duplicate Geographic Area groups into the project they duplicate.

A single real-world project can exist twice in the group table: once as the
project record and once as a Geographic Area carrying the boundary geometry
(``project_area``). This migration copies the geometry onto the project
record, re-points everything that referenced the Geographic Area, and then
deletes the Geographic Area row so one project is one record.

``group_type`` is not provenance. Two importers claim rows by name:
``cli/project_area_import.py`` matches only ``group_type == 'Geographic Area'``
and creates a row when it misses, while ``transfers/group_transfer.py`` matches
by name with no type filter and only upgrades a row to ``'Monitoring Plan'``
when one of its wells is currently monitored. Whichever ran first decides the
surviving row's type, so a legacy NM_Aquifer project may live as a Monitoring
Plan, as ``group_type = NULL``, or as a Geographic Area. Merge targets are
therefore any group that is not itself a Geographic Area, and a target's
``group_type`` is left exactly as found.

That same collision makes deletion dangerous in one specific case: a Geographic
Area whose name is a legacy project name *is* that project's row, not a
duplicate of one. ``PROTECTED_NAMES`` refuses those outright. Both foreign keys
into a group -- ``group_thing_association.group_id`` and
``group.parent_group_id`` -- are ``ON DELETE CASCADE``, so deleting one would
take its wells with it. Re-pointing is re-queried at apply time rather than
replayed from the plan for the same reason.

Matching is deliberately conservative: names are compared after case folding
and collapsing non-alphanumeric runs, and nothing else. Anything that does not
match exactly under that rule is reported, never guessed at. Reviewed pairs
that the rule cannot see go in ``MANUAL_MATCHES``; those were chosen from a
well-membership analysis (ProjectLocations.csv joined to Location.csv,
point-in-polygon against each boundary) rather than from name similarity,
because the two name sets come from different systems.

Duplicates knowingly left out of ``MANUAL_MATCHES`` because they need a
decision rather than a reading:

* ``Tiffany Fire`` contains ``Tiffany Fire Recovery`` and ``Tiffany Fire
  Restoration`` at 100% each, with identical well counts -- those two plans are
  duplicates of each other, which is a different ticket.
* ``Eastern Tularosa Basin`` and ``Northeastern Tularosa Basin`` both point at
  the single ``Tularosa Basin`` plan, and this migration merges one Geographic
  Area into one target, so someone has to say which boundary wins first.
* ``San Juan Basin`` scores highly against ``Animas River`` only because the
  Animas is a tributary inside the basin. Containment is not identity.

Run the dry run and review its report before applying:

    oco data-migrations run 20260810_0001_consolidate_geographic_area_groups --dry-run
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.group import Group, GroupThingAssociation
from transfers.logger import logger

GEOGRAPHIC_AREA = "Geographic Area"
HISTORICAL = "Historical"

# Geographic Area rows that are really the legacy NM_Aquifer project's own row,
# identified by their name appearing in the Project column of the legacy
# Projects table. Merging one deletes a project and cascades away its wells.
#
# This list is hard-coded rather than read from the legacy CSV because
# transfers/data/nma_csv_cache is gitignored and absent outside a developer
# machine. Regenerate it against a fresh cache with:
#
#     set(pd.read_csv(".../Projects.csv")["Project"]) & {geographic area names}
#
# Verified 2026-08-10 against 57 legacy projects and 36 geographic areas.
PROTECTED_NAMES: frozenset[str] = frozenset(
    {
        "Albuquerque Basin",
        "Colfax County",
        "Eastern Tularosa Basin",
        "Eddy County",
        "Mimbres Basin",
        "Quay County",
        "Rio Rancho",
        "San Miguel County",
        "Torrance County",
    }
)

# Reviewed pairs the normalized-name rule cannot see, as
# {geographic area name: target group name}. Both names are matched exactly,
# and an entry whose target does not exist is reported rather than applied.
MANUAL_MATCHES: dict[str, str] = {
    # Name-only readings: an abbreviation the target uses, a qualifier only the
    # Geographic Area carries, or the same words in a different order.
    "Southern Taos Valley": "S.Taos Valley",
    "Southern Sacramento Mountains": "Sacramento Mtns",
    "Sacramento Mountains Watershed Study": "SM Watershed",
    "White Sands National Monument": "White Sands",
    "La Cienega Wetlands": "La Cienega",
    "Northern Taos Plateau": "Taos Plateau",
    "ABCWUA Groundwater Recharge": "ABCWUA",
    "Española Basin and Santa Fe Area": "Espanola Basin",
    "Plains of San Agustin": "San Agustin Plains Alamosa Creek",
    # Confirmed by well membership, not by name. Percentages are the share of
    # the legacy project's wells inside the boundary and the share of the
    # boundary's wells belonging to that project; both must be high, or the
    # pair is containment rather than identity.
    "Pueblo of Picuris": "Picuris Pueblo",  # 100% / 98%
    "Arroyo Seco Area": "Arroyo Seco",  # 98.6% / 86.4%
    "El Camino Real and Spaceport America": "Jornada Del Muerto",  # 83.8% / 96.6%
    "Questa Area": "Questa Red River",  # 81.8% / 77.1%
}


@dataclass(frozen=True)
class PlannedMerge:
    """One Geographic Area that will be folded into one target group."""

    geographic_area_id: int
    geographic_area_name: str
    target_id: int
    target_name: str
    target_type: str | None
    matched_by: str
    copies_geometry: bool
    thing_links_moved: int
    thing_links_dropped: int
    child_groups_moved: int
    reparents_target: bool


@dataclass(frozen=True)
class SkippedGeographicArea:
    """A Geographic Area left untouched, and why."""

    geographic_area_id: int
    geographic_area_name: str
    reason: str


@dataclass
class ConsolidationPlan:
    merges: list[PlannedMerge] = field(default_factory=list)
    protected: list[SkippedGeographicArea] = field(default_factory=list)
    conflicts: list[SkippedGeographicArea] = field(default_factory=list)
    ambiguous: list[SkippedGeographicArea] = field(default_factory=list)
    unmatched: list[SkippedGeographicArea] = field(default_factory=list)


def _normalize(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").casefold()).strip()


def _geometries_equal(session: Session, left_id: int, right_id: int) -> bool:
    left = select(Group.project_area).where(Group.id == left_id).scalar_subquery()
    right = select(Group.project_area).where(Group.id == right_id).scalar_subquery()
    return bool(session.execute(select(func.ST_Equals(left, right))).scalar())


def build_plan(session: Session) -> ConsolidationPlan:
    """Work out every change without making any of them."""
    rows = session.execute(
        select(
            Group.id,
            Group.name,
            Group.group_type,
            Group.parent_group_id,
            Group.project_area.isnot(None).label("has_area"),
        ).where(
            (Group.group_type.is_(None)) | (Group.group_type != HISTORICAL),
        )
    ).all()

    geographic_areas = [row for row in rows if row.group_type == GEOGRAPHIC_AREA]
    # A project's row may be typed Monitoring Plan or left NULL depending on
    # which importer created it, so any non-Geographic-Area group is a possible
    # target. Historical is excluded above -- retiring a project is not merging
    # into it. The target's group_type is never changed.
    targets = [row for row in rows if row.group_type != GEOGRAPHIC_AREA]

    targets_by_normalized_name: dict[str, list] = {}
    for target_row in targets:
        targets_by_normalized_name.setdefault(_normalize(target_row.name), []).append(
            target_row
        )
    targets_by_name = {target_row.name: target_row for target_row in targets}

    thing_ids_by_group = _thing_ids_by_group(
        session, [row.id for row in geographic_areas + targets]
    )
    children_by_parent = _children_by_parent(
        session, [row.id for row in geographic_areas]
    )

    plan = ConsolidationPlan()
    for area in geographic_areas:
        if area.name in PROTECTED_NAMES:
            plan.protected.append(
                SkippedGeographicArea(
                    geographic_area_id=area.id,
                    geographic_area_name=area.name,
                    reason=(
                        "name is a legacy project name, so this row is the "
                        "project itself rather than a duplicate of one"
                    ),
                )
            )
            continue

        target, skip = _resolve_target(
            area, targets_by_name, targets_by_normalized_name
        )
        if skip is not None:
            if skip.reason.startswith("ambiguous"):
                plan.ambiguous.append(skip)
            else:
                plan.unmatched.append(skip)
            continue

        copies_geometry = area.has_area and not target.has_area
        if area.has_area and target.has_area:
            # Never clobber a target that already carries a boundary. An
            # identical geometry is not a conflict -- it is what a partially
            # applied run looks like -- so the pair still merges.
            if not _geometries_equal(session, area.id, target.id):
                plan.conflicts.append(
                    SkippedGeographicArea(
                        geographic_area_id=area.id,
                        geographic_area_name=area.name,
                        reason=(
                            f"target {target.id} ({target.name!r}) already has a "
                            "different project_area; needs review"
                        ),
                    )
                )
                continue

        area_things = thing_ids_by_group.get(area.id, set())
        target_things = thing_ids_by_group.get(target.id, set())
        children = children_by_parent.get(area.id, [])

        plan.merges.append(
            PlannedMerge(
                geographic_area_id=area.id,
                geographic_area_name=area.name,
                target_id=target.id,
                target_name=target.name,
                target_type=target.group_type,
                matched_by=(
                    "manual" if area.name in MANUAL_MATCHES else "normalized name"
                ),
                copies_geometry=copies_geometry,
                thing_links_moved=len(area_things - target_things),
                thing_links_dropped=len(area_things & target_things),
                child_groups_moved=len(
                    [child for child in children if child != target.id]
                ),
                reparents_target=target.parent_group_id == area.id,
            )
        )

    return _reject_many_to_one(plan)


def _reject_many_to_one(plan: ConsolidationPlan) -> ConsolidationPlan:
    """
    Refuse a target claimed by more than one Geographic Area.

    Applying those in sequence would look like it worked: the first merge
    copies its geometry and the rest are silently swallowed by the
    ``project_area IS NULL`` guard in the update, leaving the report claiming
    boundaries that were never written. Which boundary wins is a decision for
    a person, so report the whole set instead of picking one.
    """
    claims: dict[int, list[PlannedMerge]] = {}
    for merge in plan.merges:
        claims.setdefault(merge.target_id, []).append(merge)

    kept = []
    for merges in claims.values():
        if len(merges) == 1:
            kept.append(merges[0])
            continue
        contenders = ", ".join(
            f"{merge.geographic_area_id} ({merge.geographic_area_name!r})"
            for merge in merges
        )
        for merge in merges:
            plan.ambiguous.append(
                SkippedGeographicArea(
                    geographic_area_id=merge.geographic_area_id,
                    geographic_area_name=merge.geographic_area_name,
                    reason=(
                        f"ambiguous: target {merge.target_id} "
                        f"({merge.target_name!r}) is also claimed by {contenders}"
                    ),
                )
            )

    plan.merges = kept
    return plan


def _resolve_target(area, targets_by_name, targets_by_normalized_name):
    """Return (target row, None) or (None, SkippedGeographicArea)."""
    manual_target_name = MANUAL_MATCHES.get(area.name)
    if manual_target_name is not None:
        target = targets_by_name.get(manual_target_name)
        if target is None:
            return None, SkippedGeographicArea(
                geographic_area_id=area.id,
                geographic_area_name=area.name,
                reason=(
                    f"manual match target {manual_target_name!r} is not an "
                    "existing non-Geographic-Area group"
                ),
            )
        return target, None

    candidates = targets_by_normalized_name.get(_normalize(area.name), [])
    if not candidates:
        return None, SkippedGeographicArea(
            geographic_area_id=area.id,
            geographic_area_name=area.name,
            reason="no matching group",
        )
    if len(candidates) > 1:
        return None, SkippedGeographicArea(
            geographic_area_id=area.id,
            geographic_area_name=area.name,
            reason=(
                "ambiguous: matches groups "
                + ", ".join(f"{row.id} ({row.name!r})" for row in candidates)
            ),
        )
    return candidates[0], None


def _thing_ids_by_group(session: Session, group_ids: list[int]) -> dict[int, set[int]]:
    if not group_ids:
        return {}
    rows = session.execute(
        select(
            GroupThingAssociation.group_id,
            GroupThingAssociation.thing_id,
        ).where(GroupThingAssociation.group_id.in_(group_ids))
    ).all()
    mapping: dict[int, set[int]] = {}
    for row in rows:
        mapping.setdefault(row.group_id, set()).add(row.thing_id)
    return mapping


def _children_by_parent(
    session: Session, parent_ids: list[int]
) -> dict[int, list[int]]:
    if not parent_ids:
        return {}
    rows = session.execute(
        select(Group.id, Group.parent_group_id).where(
            Group.parent_group_id.in_(parent_ids)
        )
    ).all()
    mapping: dict[int, list[int]] = {}
    for row in rows:
        mapping.setdefault(row.parent_group_id, []).append(row.id)
    return mapping


def log_plan(plan: ConsolidationPlan) -> None:
    logger.info(
        "Geographic Area consolidation: %s merge(s), %s protected, "
        "%s conflict(s), %s ambiguous, %s unmatched",
        len(plan.merges),
        len(plan.protected),
        len(plan.conflicts),
        len(plan.ambiguous),
        len(plan.unmatched),
    )
    for merge in plan.merges:
        logger.info(
            "  merge group %s (%r) into %s (%r, type=%s) [%s]: geometry=%s, "
            "thing links moved=%s dropped=%s, child groups moved=%s%s",
            merge.geographic_area_id,
            merge.geographic_area_name,
            merge.target_id,
            merge.target_name,
            merge.target_type or "NULL",
            merge.matched_by,
            "copy" if merge.copies_geometry else "unchanged",
            merge.thing_links_moved,
            merge.thing_links_dropped,
            merge.child_groups_moved,
            ", reparents the target" if merge.reparents_target else "",
        )
    for label, skipped in (
        ("protected", plan.protected),
        ("conflict", plan.conflicts),
        ("ambiguous", plan.ambiguous),
        ("unmatched", plan.unmatched),
    ):
        for item in skipped:
            logger.info(
                "  %s: group %s (%r) left untouched -- %s",
                label,
                item.geographic_area_id,
                item.geographic_area_name,
                item.reason,
            )


def _apply_merge(session: Session, merge: PlannedMerge) -> None:
    area_id = merge.geographic_area_id
    target_id = merge.target_id

    if merge.copies_geometry:
        source_area = (
            select(Group.project_area).where(Group.id == area_id).scalar_subquery()
        )
        session.execute(
            update(Group)
            .where(Group.id == target_id, Group.project_area.is_(None))
            .values(project_area=source_area)
        )

    # Re-query the links rather than trusting the plan: both foreign keys
    # cascade on delete, so anything still pointing at the Geographic Area when
    # it is removed is destroyed with it.
    target_thing_ids = select(GroupThingAssociation.thing_id).where(
        GroupThingAssociation.group_id == target_id
    )
    session.execute(
        delete(GroupThingAssociation).where(
            GroupThingAssociation.group_id == area_id,
            GroupThingAssociation.thing_id.in_(target_thing_ids),
        )
    )
    session.execute(
        update(GroupThingAssociation)
        .where(GroupThingAssociation.group_id == area_id)
        .values(group_id=target_id)
    )

    if merge.reparents_target:
        # The target hangs off the Geographic Area being deleted. Re-pointing
        # it at itself is not an option, so it inherits the Geographic Area's
        # own parent.
        area_parent = (
            select(Group.parent_group_id).where(Group.id == area_id).scalar_subquery()
        )
        session.execute(
            update(Group)
            .where(Group.id == target_id)
            .values(parent_group_id=area_parent)
        )

    session.execute(
        update(Group)
        .where(Group.parent_group_id == area_id, Group.id != target_id)
        .values(parent_group_id=target_id)
    )

    session.execute(delete(Group).where(Group.id == area_id))
    session.commit()


def run(session: Session) -> None:
    plan = build_plan(session)
    log_plan(plan)
    for merge in plan.merges:
        _apply_merge(session, merge)
    logger.info("Consolidated %s Geographic Area group(s)", len(plan.merges))


def dry_run(session: Session) -> ConsolidationPlan:
    plan = build_plan(session)
    log_plan(plan)
    return plan


MIGRATION = DataMigration(
    id="20260810_0001_consolidate_geographic_area_groups",
    alembic_revision="66ac1af4ba69",
    name="Consolidate duplicate Geographic Area groups",
    description=(
        "BDMS-1143. Copies project_area geometry from each duplicate "
        "Geographic Area group onto the group that already represents the "
        "project (typed Monitoring Plan or left NULL, whichever the importers "
        "produced), re-points linked things and child groups, then deletes "
        "the Geographic Area. Geographic Areas named after a legacy project "
        "are protected because they are that project's row. Targets already "
        "carrying a different project_area, ambiguous name matches, and "
        "Geographic Areas with no counterpart are reported and left untouched."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)
