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
BDMS-1143: collapse duplicate groups so one real-world project is one record.

A single real-world project can exist twice in the group table: once as the
project record and once as a Geographic Area carrying the boundary geometry
(``project_area``). The main pass copies the geometry onto the project
record, re-points everything that referenced the Geographic Area, and then
deletes the Geographic Area row so one project is one record.

A first pass runs before it for the duplicates that pass cannot see: two
*project* rows that duplicate each other. Nothing about their names says which
is which, so ``DUPLICATE_PLAN_OPERATIONS`` lists them explicitly, each entry
reviewed by hand against well membership. That pass also renames survivors,
which is what lets the Geographic Area pass find targets it otherwise could
not -- ``Tiffany Fire`` is only resolvable once one of the two Tiffany plans
carries that name.

``group_type`` is not provenance. Two importers claimed rows by name:
``cli/project_area_import.py`` used to match only
``group_type == 'Geographic Area'`` and create a row when it missed, while
``transfers/group_transfer.py`` matches by name with no type filter and only
upgrades a row to ``'Monitoring Plan'`` when one of its wells is currently
monitored. Whichever ran first decided the surviving row's type, so a legacy
NM_Aquifer project may live as a Monitoring Plan, as ``group_type = NULL``, or
as a Geographic Area. Merge targets are therefore any group that is not itself
a Geographic Area, and a target's ``group_type`` is left exactly as found.

That same collision makes deletion dangerous in one specific case: a Geographic
Area whose name is a legacy project name *is* that project's row, not a
duplicate of one. ``PROTECTED_NAMES`` refuses those outright. Both foreign keys
into a group -- ``group_thing_association.group_id`` and
``group.parent_group_id`` -- are ``ON DELETE CASCADE``, so deleting one would
take its wells with it. Re-pointing is re-queried at apply time rather than
replayed from the plan for the same reason.

Publication travels with the boundary. ``ogc_project_areas`` serves
``project_area IS NOT NULL AND release_status = 'public'``, so moving a polygon
off a public Geographic Area and onto a draft project row would drop it from
the public layer silently -- the row simply stops matching the predicate. Where
the Geographic Area was public, the target is published to match. Never the
reverse: a target that is already public is left alone, and nothing is
published whose Geographic Area was not already visible.

Matching is deliberately conservative: names are compared after case folding
and collapsing non-alphanumeric runs, and nothing else. Anything that does not
match exactly under that rule is reported, never guessed at. Reviewed pairs
that the rule cannot see go in ``MANUAL_MATCHES``; those were chosen from a
well-membership analysis (ProjectLocations.csv joined to Location.csv,
point-in-polygon against each boundary) rather than from name similarity,
because the two name sets come from different systems.

Duplicates knowingly left out of ``MANUAL_MATCHES`` because they need a
decision rather than a reading:

* ``Eastern Tularosa Basin`` and ``Northeastern Tularosa Basin`` both point at
  the single ``Tularosa Basin`` plan, and this migration merges one Geographic
  Area into one target, so someone has to say which boundary wins first.
* ``San Juan Basin`` scores highly against ``Animas River`` only because the
  Animas is a tributary inside the basin. Containment is not identity.

Everything downstream of the first pass speaks post-rename names. A
``MANUAL_MATCHES`` value naming a group that the first pass renames would fail
soft -- ``_resolve_target`` reports a missing target and the boundary quietly
never lands -- so ``test_manual_matches_do_not_reference_a_renamed_group``
pins the rule instead of relying on it being noticed.

Run the dry run and review its report before applying:

    oco data-migrations run 20260810_0001_consolidate_geographic_area_groups --dry-run

Apply this migration by id, never through ``run-all``: registry order is
filename-alphabetical, which puts the publish migration before this one. See
``docs/bdms-1143-geographic-area-consolidation-runbook.md`` for the
verification queries.

Run this before ``oco import-project-area-boundaries``. The importer claims
features by OBJECTID and writes to whatever group owns the mapped name, so
running it second lands each boundary on the surviving row. Running it first is
not destructive but is wasted work: the project row gets a fresh boundary while
the Geographic Area still holds its stale one, and the conflict guard below
then reports that pair and skips it.
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

# The only release_status the OGC views recognise. The lexicon category also
# contains 'published' and 'final', which no view predicate matches, so compare
# against this literal rather than anything that merely reads as released.
PUBLIC = "public"

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
    # Post-rename name. DUPLICATE_PLAN_OPERATIONS renames 'Sacramento Mtns'
    # before this pass runs.
    "Southern Sacramento Mountains": "Sacramento Mountains",
    "White Sands National Monument": "White Sands",
    "Arroyo Hondo Area": "Arroyo Hondo",
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
class DuplicatePlanOperation:
    """One reviewed duplicate-project fix: fold a row away, rename, or both."""

    keep_name: str
    delete_name: str | None  # None means rename-only
    group_type: str | None  # expected on both rows
    membership: str  # see _MEMBERSHIP_RULES
    rename_to: str | None
    expected_keep_id: int | None  # advisory: reported, never a gate
    expected_delete_id: int | None
    note: str


# What the two memberships must look like for the operation to be the one that
# was reviewed. Checked against live data at apply time, because a pair that
# has diverged since the review is a different question than the one answered.
_MEMBERSHIP_RULES = ("identical", "superset", "disjoint", "none")

# Keyed by name and group_type rather than by id: uq_group_name_type makes that
# pair unique, and ids are NOT stable across environments -- on staging
# 'water Level Network' is 126, on production 126 is 'Copper Replacement
# Deposits'. Deleting by id would destroy the wrong group there. The ids below
# are the staging values, reported when they disagree so a surprise is visible,
# never used to select a row.
DUPLICATE_PLAN_OPERATIONS: tuple[DuplicatePlanOperation, ...] = (
    DuplicatePlanOperation(
        keep_name="Tiffany Fire Restoration",
        delete_name="Tiffany Fire Recovery",
        group_type="Monitoring Plan",
        membership="identical",
        rename_to="Tiffany Fire",
        expected_keep_id=20,
        expected_delete_id=47,
        note=(
            "Both plans hold the same 277 wells. Either could survive; the "
            "lower id is kept. The rename is what lets the Geographic Area "
            "pass match 'Tiffany Fire' (id 119) and hand over its boundary."
        ),
    ),
    DuplicatePlanOperation(
        keep_name="Sacramento Mtns",
        delete_name="SM Watershed",
        group_type="Monitoring Plan",
        membership="superset",
        rename_to="Sacramento Mountains",
        expected_keep_id=5,
        expected_delete_id=8,
        note=(
            "'SM Watershed' holds 492 wells, all of them also in 'Sacramento "
            "Mtns' (493), so keeping the superset loses nothing. Its boundary "
            "arrives from Geographic Area 'Southern Sacramento Mountains'."
        ),
    ),
    DuplicatePlanOperation(
        keep_name="Water Level Network",
        delete_name="water Level Network",
        group_type="Monitoring Plan",
        membership="disjoint",
        rename_to=None,
        expected_keep_id=39,
        expected_delete_id=126,
        note=(
            "A capitalisation typo that became its own group. The two names "
            "differ only in case, so lookup has to be case-sensitive: "
            "_normalize casefolds and cannot tell these apart."
        ),
    ),
    DuplicatePlanOperation(
        keep_name="San Acacia",
        delete_name=None,
        group_type="Monitoring Plan",
        membership="none",
        rename_to="San Acacia Reach",
        expected_keep_id=56,
        expected_delete_id=None,
        note=(
            "Rename only, so the boundary the importer pulls for the "
            "'San Acacia Reach' study area lands on this plan instead of "
            "creating a second row beside it."
        ),
    ),
)


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
    publishes_target: bool
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


@dataclass(frozen=True)
class PlannedPlanMerge:
    """One duplicate-project operation that will be applied."""

    keep_id: int
    keep_name: str
    delete_id: int | None
    delete_name: str | None
    group_type: str | None
    renames_to: str | None
    membership: str
    thing_links_moved: int
    thing_links_dropped: int
    id_notes: tuple[str, ...]


@dataclass(frozen=True)
class SkippedPlanOperation:
    """A duplicate-project operation left untouched, and why."""

    keep_name: str
    delete_name: str | None
    reason: str


@dataclass
class ConsolidationPlan:
    merges: list[PlannedMerge] = field(default_factory=list)
    protected: list[SkippedGeographicArea] = field(default_factory=list)
    conflicts: list[SkippedGeographicArea] = field(default_factory=list)
    ambiguous: list[SkippedGeographicArea] = field(default_factory=list)
    unmatched: list[SkippedGeographicArea] = field(default_factory=list)
    plan_merges: list[PlannedPlanMerge] = field(default_factory=list)
    plan_refused: list[SkippedPlanOperation] = field(default_factory=list)
    plan_already_applied: list[SkippedPlanOperation] = field(default_factory=list)


def _normalize(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").casefold()).strip()


def _geometries_equal(session: Session, left_id: int, right_id: int) -> bool:
    left = select(Group.project_area).where(Group.id == left_id).scalar_subquery()
    right = select(Group.project_area).where(Group.id == right_id).scalar_subquery()
    return bool(session.execute(select(func.ST_Equals(left, right))).scalar())


def _lookup_group(session: Session, name: str, group_type: str | None) -> list:
    """Every group with exactly this name and type. Case-sensitive by design."""
    stmt = select(
        Group.id,
        Group.name,
        Group.group_type,
        Group.parent_group_id,
        Group.project_area.isnot(None).label("has_area"),
    ).where(Group.name == name)
    stmt = stmt.where(
        Group.group_type.is_(None)
        if group_type is None
        else Group.group_type == group_type
    )
    return session.execute(stmt).all()


def _membership_holds(rule: str, keep: set[int], delete: set[int]) -> bool:
    if rule == "identical":
        return keep == delete
    if rule == "superset":
        return delete <= keep
    if rule == "disjoint":
        return not (keep & delete)
    return True  # "none": there is no row to compare against


def _describe_membership(keep: set[int], delete: set[int]) -> str:
    return (
        f"keep holds {len(keep)}, delete holds {len(delete)}, "
        f"{len(keep & delete)} shared, {len(delete - keep)} only in delete"
    )


def _resolve_plan_operation(
    session: Session, operation: DuplicatePlanOperation
) -> tuple[PlannedPlanMerge | None, SkippedPlanOperation | None, bool]:
    """Return (planned, refusal, already_applied). At most one is meaningful."""

    def refuse(reason: str):
        return (
            None,
            SkippedPlanOperation(
                keep_name=operation.keep_name,
                delete_name=operation.delete_name,
                reason=reason,
            ),
            False,
        )

    if operation.membership not in _MEMBERSHIP_RULES:
        return refuse(f"unknown membership rule {operation.membership!r}")
    if operation.membership == "none" and operation.delete_name is not None:
        # "none" means there is no second row, so _membership_holds has nothing
        # to compare and returns True. Pairing it with a deletion would read as
        # "no constraint" and silently skip the one check that stops a mis-merge.
        return refuse(
            "membership 'none' is only valid for a rename-only operation, "
            f"but this one deletes {operation.delete_name!r}"
        )
    if operation.keep_name in PROTECTED_NAMES or (
        operation.delete_name in PROTECTED_NAMES
    ):
        return refuse("names a protected legacy project row")

    # Accept the post-rename name too, so a half-applied run resolves forward
    # instead of refusing on work it already did.
    survivors = _lookup_group(session, operation.keep_name, operation.group_type)
    renamed = (
        _lookup_group(session, operation.rename_to, operation.group_type)
        if operation.rename_to
        else []
    )
    if len(survivors) == 1 and renamed:
        # Both names are live, so this is not a half-applied run: some other
        # group already owns the name the survivor would take.
        return refuse(
            f"group {renamed[0].id} already holds "
            f"({operation.rename_to!r}, {operation.group_type or 'NULL'}), "
            "which uq_group_name_type forbids duplicating"
        )
    if len(survivors) + len(renamed) != 1:
        return refuse(
            f"expected exactly one group named {operation.keep_name!r} "
            f"(or {operation.rename_to!r}) of type "
            f"{operation.group_type or 'NULL'}, found "
            f"{len(survivors) + len(renamed)}"
        )
    keep = (survivors or renamed)[0]
    already_renamed = not survivors

    to_delete = (
        _lookup_group(session, operation.delete_name, operation.group_type)
        if operation.delete_name
        else []
    )
    if len(to_delete) > 1:
        return refuse(
            f"{len(to_delete)} groups named {operation.delete_name!r} of type "
            f"{operation.group_type or 'NULL'}; refusing to pick one"
        )
    if operation.delete_name and not to_delete:
        if already_renamed or operation.rename_to is None:
            return (
                None,
                SkippedPlanOperation(
                    keep_name=operation.keep_name,
                    delete_name=operation.delete_name,
                    reason="already applied",
                ),
                True,
            )
        return refuse(
            f"no group named {operation.delete_name!r} of type "
            f"{operation.group_type or 'NULL'}, but the survivor still carries "
            "its original name, so this is not a completed run"
        )
    if not operation.delete_name and already_renamed:
        return (
            None,
            SkippedPlanOperation(
                keep_name=operation.keep_name,
                delete_name=None,
                reason="already applied",
            ),
            True,
        )

    delete = to_delete[0] if to_delete else None

    if delete is not None:
        if delete.has_area:
            return refuse(
                f"group {delete.id} ({delete.name!r}) holds a project_area; "
                "this pass has no geometry-copy path and deleting it would "
                "destroy the boundary"
            )
        children = session.execute(
            select(Group.id).where(Group.parent_group_id == delete.id)
        ).all()
        if children:
            return refuse(
                f"group {delete.id} ({delete.name!r}) has "
                f"{len(children)} child group(s), which ON DELETE CASCADE "
                "would take with it"
            )
        if keep.parent_group_id == delete.id:
            return refuse(
                f"the survivor hangs off group {delete.id} ({delete.name!r}); "
                "re-parenting is not this pass's job"
            )

    ids_by_group = _thing_ids_by_group(
        session, [group.id for group in (keep, delete) if group is not None]
    )
    keep_things = ids_by_group.get(keep.id, set())
    delete_things = ids_by_group.get(delete.id, set()) if delete else set()
    if not _membership_holds(operation.membership, keep_things, delete_things):
        return refuse(
            f"expected {operation.membership} membership, but "
            f"{_describe_membership(keep_things, delete_things)}"
        )

    if operation.rename_to and not already_renamed:
        # The (rename_to, group_type) pair is already known to be free: the
        # survivor lookup above refuses when both names are live.
        #
        # A second non-Geographic-Area group normalizing the same way would make
        # the Geographic Area pass ambiguous the moment it looked for a target.
        clashes = session.execute(
            select(Group.id, Group.name).where(
                Group.group_type.is_distinct_from(GEOGRAPHIC_AREA),
                Group.id.not_in([group.id for group in (keep, delete) if group]),
            )
        ).all()
        clashes = [
            row
            for row in clashes
            if _normalize(row.name) == _normalize(operation.rename_to)
        ]
        if clashes:
            return refuse(
                f"renaming to {operation.rename_to!r} would collide with group "
                f"{clashes[0].id} ({clashes[0].name!r}) once names are "
                "normalized, leaving the Geographic Area pass ambiguous"
            )

    id_notes = []
    if operation.expected_keep_id is not None and keep.id != operation.expected_keep_id:
        id_notes.append(
            f"survivor is id {keep.id}, review recorded "
            f"{operation.expected_keep_id}"
        )
    if (
        delete is not None
        and operation.expected_delete_id is not None
        and delete.id != operation.expected_delete_id
    ):
        id_notes.append(
            f"deleted row is id {delete.id}, review recorded "
            f"{operation.expected_delete_id}"
        )

    return (
        PlannedPlanMerge(
            keep_id=keep.id,
            keep_name=keep.name,
            delete_id=delete.id if delete else None,
            delete_name=delete.name if delete else None,
            group_type=operation.group_type,
            renames_to=None if already_renamed else operation.rename_to,
            membership=operation.membership,
            thing_links_moved=len(delete_things - keep_things),
            thing_links_dropped=len(delete_things & keep_things),
            id_notes=tuple(id_notes),
        ),
        None,
        False,
    )


def resolve_plan_operations(session: Session) -> ConsolidationPlan:
    """Resolve the hand-reviewed duplicate-project pass. Writes nothing."""
    plan = ConsolidationPlan()
    for operation in DUPLICATE_PLAN_OPERATIONS:
        planned, refusal, already_applied = _resolve_plan_operation(session, operation)
        if planned is not None:
            plan.plan_merges.append(planned)
        elif already_applied:
            plan.plan_already_applied.append(refusal)
        else:
            plan.plan_refused.append(refusal)
    return plan


def build_plan(session: Session) -> ConsolidationPlan:
    """
    Work out every change without making any of them.

    The Geographic Area pass has to see the renamed world or it reports merges
    that will not happen and misses ones that will, so the duplicate-project
    pass is applied inside a SAVEPOINT that is always rolled back.
    """
    plan = resolve_plan_operations(session)
    savepoint = session.begin_nested()
    try:
        for merge in plan.plan_merges:
            _apply_plan_merge(session, merge)
        build_geographic_area_plan(session, plan)
    finally:
        savepoint.rollback()
    return plan


def build_geographic_area_plan(
    session: Session, plan: ConsolidationPlan
) -> ConsolidationPlan:
    """Fill in the Geographic Area merges for the state the session is in."""
    rows = session.execute(
        select(
            Group.id,
            Group.name,
            Group.group_type,
            Group.parent_group_id,
            Group.release_status,
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
                # Not gated on copies_geometry: when both rows already carry the
                # same polygon nothing is copied, but the public source row is
                # still deleted, so a draft target would still cost the layer a
                # row.
                publishes_target=(
                    area.release_status == PUBLIC and target.release_status != PUBLIC
                ),
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
    log_plan_operations(plan)
    log_geographic_area_plan(plan)


def log_plan_operations(plan: ConsolidationPlan) -> None:
    logger.info(
        "Duplicate project consolidation: %s operation(s), %s refused, "
        "%s already applied",
        len(plan.plan_merges),
        len(plan.plan_refused),
        len(plan.plan_already_applied),
    )
    for merge in plan.plan_merges:
        logger.info(
            "  keep group %s (%r, type=%s)%s%s: thing links moved=%s "
            "dropped=%s, membership=%s%s",
            merge.keep_id,
            merge.keep_name,
            merge.group_type or "NULL",
            (
                f", delete {merge.delete_id} ({merge.delete_name!r})"
                if merge.delete_id is not None
                else ""
            ),
            f", rename to {merge.renames_to!r}" if merge.renames_to else "",
            merge.thing_links_moved,
            merge.thing_links_dropped,
            merge.membership,
            f" [{'; '.join(merge.id_notes)}]" if merge.id_notes else "",
        )
    for label, skipped in (
        ("refused", plan.plan_refused),
        ("already applied", plan.plan_already_applied),
    ):
        for item in skipped:
            logger.info(
                "  %s: %r / %r -- %s",
                label,
                item.keep_name,
                item.delete_name,
                item.reason,
            )


def log_geographic_area_plan(plan: ConsolidationPlan) -> None:
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
            "thing links moved=%s dropped=%s, child groups moved=%s%s%s",
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
            ", publishes the target" if merge.publishes_target else "",
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

    if merge.publishes_target:
        # The boundary was on the public layer before this merge. Deleting the
        # row that carried it would take it off unless the row inheriting it is
        # public too.
        session.execute(
            update(Group).where(Group.id == target_id).values(release_status=PUBLIC)
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


def _apply_plan_merge(session: Session, merge: PlannedPlanMerge) -> None:
    """
    Fold one duplicate project into another and rename the survivor.

    Same cascade reasoning as ``_apply_merge``: the links are re-queried here
    rather than replayed from the plan, because anything still pointing at the
    deleted row when it goes is destroyed with it.
    """
    if merge.delete_id is not None:
        survivor_thing_ids = select(GroupThingAssociation.thing_id).where(
            GroupThingAssociation.group_id == merge.keep_id
        )
        session.execute(
            delete(GroupThingAssociation).where(
                GroupThingAssociation.group_id == merge.delete_id,
                GroupThingAssociation.thing_id.in_(survivor_thing_ids),
            )
        )
        session.execute(
            update(GroupThingAssociation)
            .where(GroupThingAssociation.group_id == merge.delete_id)
            .values(group_id=merge.keep_id)
        )
        # Delete before renaming, so the rename can never collide with the row
        # on its way out.
        session.execute(delete(Group).where(Group.id == merge.delete_id))

    if merge.renames_to is not None:
        session.execute(
            update(Group).where(Group.id == merge.keep_id).values(name=merge.renames_to)
        )


def run(session: Session) -> None:
    plan = resolve_plan_operations(session)
    log_plan_operations(plan)
    for plan_merge in plan.plan_merges:
        _apply_plan_merge(session, plan_merge)
        session.commit()

    # Built only now: the Geographic Area pass matches on name, and the pass
    # above has just changed some of them.
    build_geographic_area_plan(session, plan)
    log_geographic_area_plan(plan)
    for merge in plan.merges:
        _apply_merge(session, merge)
        session.commit()

    logger.info(
        "Consolidated %s duplicate project(s) and %s Geographic Area group(s)",
        len(plan.plan_merges),
        len(plan.merges),
    )


def dry_run(session: Session) -> ConsolidationPlan:
    plan = build_plan(session)
    log_plan(plan)
    return plan


MIGRATION = DataMigration(
    id="20260810_0001_consolidate_geographic_area_groups",
    alembic_revision="66ac1af4ba69",
    name="Consolidate duplicate groups",
    description=(
        "BDMS-1143. First folds together the hand-reviewed pairs of project "
        "rows that duplicate each other (Tiffany Fire, Sacramento Mtns, Water "
        "Level Network) and renames the survivors, which is what lets the "
        "second pass find targets such as 'Tiffany Fire' at all. Then copies "
        "project_area geometry from each duplicate "
        "Geographic Area group onto the group that already represents the "
        "project (typed Monitoring Plan or left NULL, whichever the importers "
        "produced), re-points linked things and child groups, publishes the "
        "target when the Geographic Area it inherits from was public so the "
        "boundary stays on ogc_project_areas, then deletes "
        "the Geographic Area. Geographic Areas named after a legacy project "
        "are protected because they are that project's row. Targets already "
        "carrying a different project_area, ambiguous name matches, and "
        "Geographic Areas with no counterpart are reported and left untouched."
    ),
    run=run,
    is_repeatable=False,
    dry_run=dry_run,
)
