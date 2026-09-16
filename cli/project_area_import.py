"""
Pull study-area boundaries from the Aquifer Mapping Study Areas layer.

Every feature is claimed by OBJECTID, not by its ``location`` attribute. Two
reasons, both load-bearing:

* ``location`` is not unique in the layer. OBJECTIDs 9 and 42 are both
  ``Estancia Basin``, 6 and 39 are both ``Mimbres Basin``, and 40 and 41 are
  both ``Gila-Animas``. Matching on the attribute would overwrite an existing
  boundary with a different area's polygon, and would try to insert two rows
  with the same ``(name, group_type)``, which ``uq_group_name_type`` forbids.
* A boundary's owner is not always named after the feature. Consolidation
  (``20260810_0001_consolidate_geographic_area_groups``) folds a Geographic
  Area into the project row it duplicated, so the polygon for
  ``Southern Taos Valley`` now lives on the plan called ``S.Taos Valley``.
  ``PROJECT_AREA_MAPPINGS`` records the owner, which is why re-importing no
  longer recreates the rows that migration deletes.

The map is therefore an allowlist as well as a translation: a feature whose
OBJECTID is absent is reported and skipped, never written and never created.
``create_if_missing`` is set only for areas that have no group yet; for
everything else a missing name means the world is not in the state this map
describes -- most likely the consolidation has not run -- and creating a
Geographic Area would silently reintroduce the duplicate. That is reported
instead.

Run the dry run first. It writes nothing and prints one line per action:

    oco import-project-area-boundaries --dry-run
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from geoalchemy2 import WKTElement
from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy import func, select

from db import Group
from db.engine import session_ctx
from transfers.logger import logger

# Layer 17 was retired and now 404s; the study areas moved to 18. This URL is
# load-bearing rather than incidental, so it lives here only -- the CLI takes
# its default from this constant instead of repeating the string.
PROJECT_AREA_LAYER_URL = "".join(
    [
        "https://maps.nmt.edu/server/rest/services/Water/",
        "Water_Resources/MapServer/18",
    ]
)
PROJECT_AREA_PAGE_SIZE = 1000

GEOGRAPHIC_AREA = "Geographic Area"
PUBLIC = "public"


@dataclass(frozen=True)
class ProjectAreaMapping:
    """Which group owns one layer feature's boundary."""

    group_name: str
    create_if_missing: bool = False
    note: str = ""


# Keyed by OBJECTID. Names are the ones that exist *after* consolidation.
#
# The (AEM) suffix marks a study area mapped with airborne electromagnetic
# (AEM) data. Those areas are why the key has to be the OBJECTID: each one
# shares its layer ``location`` with an older area of the same name, so
# OBJECTIDs 9 and 42 are both 'Estancia Basin' and 6 and 39 are both
# 'Mimbres Basin'. The suffix exists only here and in the group name, not
# upstream.
PROJECT_AREA_MAPPINGS: dict[int, ProjectAreaMapping] = {
    1: ProjectAreaMapping("San Juan Basin"),
    2: ProjectAreaMapping("Central High Plains"),
    3: ProjectAreaMapping("Pecos Slope"),
    4: ProjectAreaMapping("Salt Basin"),
    5: ProjectAreaMapping("Curry Roosevelt Quay Region"),
    6: ProjectAreaMapping("Mimbres Basin", note="the legacy area, not 39's AEM study"),
    7: ProjectAreaMapping("Delaware Basin"),
    8: ProjectAreaMapping("Rio Arriba County", create_if_missing=True),
    9: ProjectAreaMapping("Estancia Basin", note="the legacy area, not 42's AEM study"),
    10: ProjectAreaMapping("Roswell Artesian Basin"),
    11: ProjectAreaMapping(
        "San Agustin Plains Alamosa Creek",
        note="location is 'Plains of San Agustin'; consolidation kept the plan name",
    ),
    12: ProjectAreaMapping(
        "Carrizozo",
        note="a Monitoring Plan with no boundary until this import gives it one",
    ),
    13: ProjectAreaMapping("High Plains Aquifer Monitoring"),
    14: ProjectAreaMapping("Taos Plateau", note="location is 'Northern Taos Plateau'"),
    15: ProjectAreaMapping("Union County"),
    16: ProjectAreaMapping(
        "Jornada Del Muerto",
        note="location is 'El Camino Real and Spaceport America'",
    ),
    17: ProjectAreaMapping("Northeastern Tularosa Basin"),
    18: ProjectAreaMapping("Eastern Tularosa Basin"),
    19: ProjectAreaMapping(
        "Middle Rio Grande Aquifer Storage and Recovery", create_if_missing=True
    ),
    20: ProjectAreaMapping(
        "San Acacia Reach",
        note=(
            "the 'San Acacia' plan, renamed by the consolidation so this "
            "boundary lands on it instead of creating a second row"
        ),
    ),
    21: ProjectAreaMapping("Animas River"),
    22: ProjectAreaMapping("Rio Rancho"),
    23: ProjectAreaMapping("Albuquerque Water Table", create_if_missing=True),
    24: ProjectAreaMapping(
        "White Sands", note="location is 'White Sands National Monument'"
    ),
    25: ProjectAreaMapping("Sunshine Valley"),
    26: ProjectAreaMapping("Truth or Consequences"),
    27: ProjectAreaMapping("ABCWUA", note="location is 'ABCWUA Groundwater Recharge'"),
    28: ProjectAreaMapping("Springs of the Rio Grande Gorge"),
    29: ProjectAreaMapping("S.Taos Valley", note="location is 'Southern Taos Valley'"),
    30: ProjectAreaMapping("Questa Red River", note="location is 'Questa Area'"),
    31: ProjectAreaMapping("Snowy River"),
    32: ProjectAreaMapping("Magdalena"),
    33: ProjectAreaMapping("La Cienega", note="location is 'La Cienega Wetlands'"),
    34: ProjectAreaMapping(
        "Tiffany Fire",
        note="the surviving Tiffany plan, renamed by the consolidation",
    ),
    35: ProjectAreaMapping("Sacramento Mountains Watershed Study"),
    36: ProjectAreaMapping("Pena Blanca"),
    37: ProjectAreaMapping("Middle Rio Grande (AEM)", create_if_missing=True),
    38: ProjectAreaMapping("Lower Rio Grande (AEM)", create_if_missing=True),
    39: ProjectAreaMapping(
        "Mimbres Basin (AEM)",
        create_if_missing=True,
        note="shares the location 'Mimbres Basin' with OBJECTID 6",
    ),
    40: ProjectAreaMapping(
        "Gila-Animas 1 (AEM)",
        create_if_missing=True,
        note="shares the location 'Gila-Animas' with OBJECTID 41",
    ),
    41: ProjectAreaMapping(
        "Gila-Animas 2 (AEM)",
        create_if_missing=True,
        note="shares the location 'Gila-Animas' with OBJECTID 40",
    ),
    42: ProjectAreaMapping(
        "Estancia Basin (AEM)",
        create_if_missing=True,
        note="shares the location 'Estancia Basin' with OBJECTID 9",
    ),
    43: ProjectAreaMapping("Taos", create_if_missing=True),
    44: ProjectAreaMapping(
        "Espanola Basin",
        note="location is 'Española Basin and Santa Fe Area'",
    ),
}

CREATE = "create"
UPDATE = "update"
UNCHANGED = "unchanged"
SKIP = "skip"


@dataclass(frozen=True)
class PlannedAreaAction:
    object_id: int | None
    location: str
    group_name: str | None
    action: str
    group_id: int | None
    publishes: bool
    reason: str
    wkt: str | None


@dataclass(frozen=True)
class ProjectAreaImportResult:
    fetched: int
    created: int
    updated: int
    unchanged: int
    published: int
    skipped: int
    actions: tuple[PlannedAreaAction, ...]

    @property
    def skips(self) -> tuple[PlannedAreaAction, ...]:
        return tuple(action for action in self.actions if action.action == SKIP)


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _geoms_equal(geom1: str, geom2: str) -> bool:
    from shapely import wkt

    return wkt.loads(geom1).equals(wkt.loads(geom2))


def _geojson_to_multipolygon_wkt(geometry: dict[str, Any]) -> str:
    geom = shape(geometry)
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    if not isinstance(geom, MultiPolygon):
        raise ValueError(
            f"Expected Polygon or MultiPolygon geometry, got {geom.geom_type}"
        )
    return geom.wkt


def _feature_object_id(feature: dict[str, Any]) -> int | None:
    """
    Dig the OBJECTID out of a GeoJSON feature.

    ArcGIS is inconsistent about where it puts the object id depending on the
    layer's configuration, and a silently missing id would skip every feature,
    so try each place it is known to land.
    """
    candidates = [feature.get("id")]
    properties = feature.get("properties") or {}
    candidates.extend(
        properties.get(key) for key in ("OBJECTID", "objectid", "OBJECTID_1")
    )
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _existing_wkt(group: Group) -> str | None:
    if group.project_area is None:
        return None
    from shapely import wkb

    return wkb.loads(bytes(group.project_area.data)).wkt


def plan_project_area_import(
    session, features: list[dict[str, Any]]
) -> list[PlannedAreaAction]:
    """Work out one action per feature without making any of them."""
    actions: list[PlannedAreaAction] = []
    # Names already spoken for by an earlier action in this same run. The
    # lookups below all read pre-run state, so without this two entries whose
    # names normalize alike would both plan a create and collide on
    # uq_group_name_type at commit, taking the whole import down with them.
    claimed: dict[str, int] = {}

    for feature in features:
        properties = feature.get("properties") or {}
        location = (properties.get("location") or "").strip()
        geometry = feature.get("geometry")
        object_id = _feature_object_id(feature)

        def skip(reason: str, group_name: str | None = None) -> PlannedAreaAction:
            return PlannedAreaAction(
                object_id=object_id,
                location=location,
                group_name=group_name,
                action=SKIP,
                group_id=None,
                publishes=False,
                reason=reason,
                wkt=None,
            )

        if object_id is None:
            actions.append(skip("feature carries no resolvable OBJECTID"))
            continue
        if geometry is None:
            actions.append(skip("feature carries no geometry"))
            continue

        mapping = PROJECT_AREA_MAPPINGS.get(object_id)
        if mapping is None:
            actions.append(skip("OBJECTID is not in PROJECT_AREA_MAPPINGS"))
            continue

        normalized = _normalize_name(mapping.group_name)
        if normalized in claimed:
            actions.append(
                skip(
                    f"OBJECTID {claimed[normalized]} already claimed "
                    f"{mapping.group_name!r} in this run",
                    mapping.group_name,
                )
            )
            continue
        claimed[normalized] = object_id

        wkt_value = _geojson_to_multipolygon_wkt(geometry)

        # No group_type filter: after consolidation a boundary's owner is often
        # a Monitoring Plan, and filtering to Geographic Area is exactly what
        # made the importer create duplicates beside those rows.
        groups = session.scalars(
            select(Group).where(func.lower(func.trim(Group.name)) == normalized)
        ).all()

        if len(groups) > 1:
            actions.append(
                skip(
                    f"name is owned by {len(groups)} groups "
                    f"({', '.join(str(group.id) for group in groups)}); "
                    "refusing to pick one",
                    mapping.group_name,
                )
            )
            continue

        if not groups:
            if not mapping.create_if_missing:
                actions.append(
                    skip(
                        "mapped name is not present, and this entry is not "
                        "allowed to create it; has the consolidation run?",
                        mapping.group_name,
                    )
                )
                continue
            actions.append(
                PlannedAreaAction(
                    object_id=object_id,
                    location=location,
                    group_name=mapping.group_name,
                    action=CREATE,
                    group_id=None,
                    publishes=True,
                    reason="no group owns this name yet",
                    wkt=wkt_value,
                )
            )
            continue

        group = groups[0]
        old_wkt = _existing_wkt(group)
        geometry_changed = old_wkt is None or not _geoms_equal(old_wkt, wkt_value)
        # Any group holding a boundary is public. That is the invariant
        # 20260714_0001 established (`UPDATE "group" SET release_status =
        # 'public' WHERE project_area IS NOT NULL`, with no predicate), and a
        # boundary that came from the public webmap has no draft provenance to
        # protect, so there is no case here where publishing reveals something
        # that was not already published at the source. This is deliberately
        # broader than the consolidation's publishes_target rule, which guards
        # a different situation: moving an existing polygon between rows, where
        # the source row may legitimately be draft.
        publishes = group.release_status != PUBLIC

        actions.append(
            PlannedAreaAction(
                object_id=object_id,
                location=location,
                group_name=mapping.group_name,
                action=UPDATE if geometry_changed or publishes else UNCHANGED,
                group_id=group.id,
                publishes=publishes,
                reason=(
                    "geometry differs upstream"
                    if geometry_changed
                    else "geometry matches; publishing only"
                ),
                wkt=wkt_value if geometry_changed else None,
            )
        )

    return actions


def _apply_area_action(session, action: PlannedAreaAction) -> None:
    if action.action == CREATE:
        session.add(
            Group(
                name=action.group_name,
                group_type=GEOGRAPHIC_AREA,
                project_area=WKTElement(action.wkt, srid=4326),
                release_status=PUBLIC,
            )
        )
        return

    if action.action != UPDATE:
        return

    group = session.get(Group, action.group_id)
    if action.wkt is not None:
        group.project_area = WKTElement(action.wkt, srid=4326)
    if action.publishes:
        group.release_status = PUBLIC


def log_actions(actions: list[PlannedAreaAction]) -> None:
    for action in actions:
        if action.action == UNCHANGED:
            continue
        logger.info(
            "  %s: OBJECTID %s (%r) -> %r%s%s",
            action.action,
            action.object_id,
            action.location,
            action.group_name,
            f" [id {action.group_id}]" if action.group_id else "",
            f" -- {action.reason}" if action.reason else "",
        )


def import_project_area_boundaries(
    layer_url: str = PROJECT_AREA_LAYER_URL,
    dry_run: bool = False,
) -> ProjectAreaImportResult:
    with httpx.Client(timeout=60.0) as client:
        features = _fetch_project_area_features(client, layer_url)

    with session_ctx() as session:
        actions = plan_project_area_import(session, features)
        log_actions(actions)

        if dry_run:
            session.rollback()
        else:
            for action in actions:
                _apply_area_action(session, action)
            session.commit()

    counts = {kind: 0 for kind in (CREATE, UPDATE, UNCHANGED, SKIP)}
    for action in actions:
        counts[action.action] += 1

    return ProjectAreaImportResult(
        fetched=len(features),
        created=counts[CREATE],
        updated=counts[UPDATE],
        unchanged=counts[UNCHANGED],
        published=sum(1 for action in actions if action.publishes),
        skipped=counts[SKIP],
        actions=tuple(actions),
    )


def _fetch_project_area_features(
    client: httpx.Client,
    layer_url: str,
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = client.get(
            f"{layer_url}/query",
            params={
                "where": "1=1",
                "outFields": "OBJECTID,location",
                # resultOffset paging is only stable against a fixed order.
                "orderByFields": "OBJECTID",
                "returnGeometry": "true",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": PROJECT_AREA_PAGE_SIZE,
            },
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("features", [])
        if not batch:
            break
        features.extend(batch)
        if not payload.get("exceededTransferLimit"):
            break
        offset += len(batch)

    return features
