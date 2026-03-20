from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from geoalchemy2 import WKTElement
from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy import func, select

from db import Group
from db.engine import session_ctx

PROJECT_AREA_LAYER_URL = "".join(
    [
        "https://maps.nmt.edu/server/rest/services/Water/",
        "Water_Resources/MapServer/17",
    ]
)
PROJECT_AREA_PAGE_SIZE = 1000


@dataclass(frozen=True)
class ProjectAreaImportResult:
    fetched: int
    matched: int
    updated: int
    unmatched_locations: tuple[str, ...]


def _normalize_name(value: str) -> str:
    return value.strip().lower()


def _geojson_to_multipolygon_wkt(geometry: dict[str, Any]) -> str:
    geom = shape(geometry)
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    if not isinstance(geom, MultiPolygon):
        raise ValueError(
            f"Expected Polygon or MultiPolygon geometry, got {geom.geom_type}"
        )
    return geom.wkt


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
                "outFields": "location",
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


def import_project_area_boundaries(
    layer_url: str = PROJECT_AREA_LAYER_URL,
) -> ProjectAreaImportResult:
    with httpx.Client(timeout=60.0) as client:
        features = _fetch_project_area_features(client, layer_url)

    unmatched_locations: list[str] = []
    matched = 0
    updated = 0

    with session_ctx() as session:
        for feature in features:
            attributes = feature.get("properties", {})
            geometry = feature.get("geometry")
            location_name = (attributes.get("location") or "").strip()

            if not location_name or geometry is None:
                continue

            groups = session.scalars(
                select(Group).where(
                    func.lower(func.trim(Group.name)) == _normalize_name(location_name)
                )
            ).all()

            if not groups:
                unmatched_locations.append(location_name)
                continue

            matched += len(groups)
            project_area = WKTElement(
                _geojson_to_multipolygon_wkt(geometry),
                srid=4326,
            )
            for group in groups:
                group.project_area = project_area
                updated += 1

        session.commit()

    return ProjectAreaImportResult(
        fetched=len(features),
        matched=matched,
        updated=updated,
        unmatched_locations=tuple(sorted(set(unmatched_locations))),
    )
