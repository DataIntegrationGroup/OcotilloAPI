from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Dict, Tuple

from fastapi import HTTPException, Request
from geoalchemy2.functions import (
    ST_AsGeoJSON,
    ST_GeomFromText,
    ST_Intersects,
    ST_MakeEnvelope,
    ST_Within,
)
from sqlalchemy import exists, func, select
from sqlalchemy.orm import aliased

from core.constants import SRID_WGS84
from db.location import Location, LocationThingAssociation
from db.thing import Thing, WellCasingMaterial, WellPurpose, WellScreen


def _parse_bbox(bbox: str) -> Tuple[float, float, float, float]:
    try:
        parts = [float(part) for part in bbox.split(",")]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid bbox format") from exc
    if len(parts) not in (4, 6):
        raise HTTPException(status_code=400, detail="bbox must have 4 or 6 values")
    return parts[0], parts[1], parts[2], parts[3]


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if isinstance(parsed, datetime):
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.combine(parsed, datetime.min.time(), tzinfo=timezone.utc)


def _parse_datetime_range(value: str) -> Tuple[datetime | None, datetime | None]:
    if "/" in value:
        start_text, end_text = value.split("/", 1)
        start = _parse_datetime(start_text) if start_text else None
        end = _parse_datetime(end_text) if end_text else None
        return start, end
    single = _parse_datetime(value)
    return single, single


def _coerce_value(value: str) -> Any:
    stripped = value.strip()
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped[1:-1]
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped


def _split_and_clauses(properties: str) -> list[str]:
    normalized = " ".join(properties.split())
    lower = normalized.lower()
    clauses = []
    start = 0
    needle = " and "
    while True:
        idx = lower.find(needle, start)
        if idx == -1:
            clause = normalized[start:].strip()
            if clause:
                clauses.append(clause)
            break
        clause = normalized[start:idx].strip()
        if clause:
            clauses.append(clause)
        start = idx + len(needle)
    return clauses


def _split_field_and_value(text: str) -> tuple[str | None, str | None]:
    left, sep, right = text.partition("=")
    if not sep:
        return None, None
    field = left.strip()
    value = right.strip()
    if not field or not value:
        return None, None
    return field, value


def _apply_properties_filter(
    query,
    properties: str,
    column_map: Dict[str, Any],
    relationship_map: Dict[str, Any] | None = None,
):
    relationship_map = relationship_map or {}
    clauses = _split_and_clauses(properties)
    for clause in clauses:
        in_match = re.match(
            r"^\s*(\w+)\s+IN\s+\((.+)\)\s*$", clause, flags=re.IGNORECASE
        )
        if in_match:
            field = in_match.group(1)
            values = [val.strip() for val in in_match.group(2).split(",")]
            if field in relationship_map:
                query = query.where(
                    relationship_map[field]([_coerce_value(v) for v in values])
                )
                continue
            if field not in column_map:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported property: {field}"
                )
            query = query.where(
                column_map[field].in_([_coerce_value(v) for v in values])
            )
            continue
        field, value = _split_field_and_value(clause)
        if field and value:
            if field in relationship_map:
                query = query.where(relationship_map[field]([_coerce_value(value)]))
                continue
            if field not in column_map:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported property: {field}"
                )
            query = query.where(column_map[field] == _coerce_value(value))
            continue
        raise HTTPException(
            status_code=400, detail=f"Unsupported CQL expression: {clause}"
        )
    return query


def _apply_cql_filter(query, filter_expr: str):
    match = re.match(
        r"^\s*(INTERSECTS|WITHIN)\s*\(\s*(geometry|geom)\s*,\s*(POLYGON|MULTIPOLYGON)\s*(\(.+\))\s*\)\s*$",
        filter_expr,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise HTTPException(status_code=400, detail="Unsupported CQL filter expression")
    op = match.group(1).upper()
    wkt = f"{match.group(3).upper()} {match.group(4)}"
    geom = ST_GeomFromText(wkt, SRID_WGS84)
    if op == "WITHIN":
        return query.where(ST_Within(Location.point, geom))
    return query.where(ST_Intersects(Location.point, geom))


def _latest_location_subquery():
    return (
        select(
            LocationThingAssociation.thing_id,
            func.max(LocationThingAssociation.effective_start).label("max_start"),
        )
        .where(LocationThingAssociation.effective_end == None)
        .group_by(LocationThingAssociation.thing_id)
        .subquery()
    )


def _location_query():
    return select(
        Location,
        ST_AsGeoJSON(Location.point).label("geojson"),
    )


def _thing_query(thing_type: str):
    lta_alias = aliased(LocationThingAssociation)
    latest_assoc = _latest_location_subquery()
    return (
        select(
            Thing,
            ST_AsGeoJSON(Location.point).label("geojson"),
        )
        .join(lta_alias, Thing.id == lta_alias.thing_id)
        .join(Location, lta_alias.location_id == Location.id)
        .join(
            latest_assoc,
            (latest_assoc.c.thing_id == lta_alias.thing_id)
            & (latest_assoc.c.max_start == lta_alias.effective_start),
        )
        .where(Thing.thing_type == thing_type)
    )


def _apply_bbox_filter(query, bbox: str):
    minx, miny, maxx, maxy = _parse_bbox(bbox)
    envelope = ST_MakeEnvelope(minx, miny, maxx, maxy, SRID_WGS84)
    return query.where(ST_Intersects(Location.point, envelope))


def _apply_datetime_filter(query, datetime_value: str, column):
    start, end = _parse_datetime_range(datetime_value)
    if start is not None:
        query = query.where(column >= start)
    if end is not None:
        query = query.where(column <= end)
    return query


def _build_feature(row, collection_id: str) -> dict[str, Any]:
    model, geojson = row
    geometry = {} if geojson is None else _safe_json(geojson)
    if collection_id == "locations":
        properties = {
            "id": model.id,
            "description": model.description,
            "county": model.county,
            "state": model.state,
            "quad_name": model.quad_name,
            "elevation": model.elevation,
        }
    else:
        properties = {
            "id": model.id,
            "name": model.name,
            "thing_type": model.thing_type,
            "first_visit_date": model.first_visit_date,
            "nma_pk_welldata": model.nma_pk_welldata,
            "well_depth": model.well_depth,
            "hole_depth": model.hole_depth,
            "well_casing_diameter": model.well_casing_diameter,
            "well_casing_depth": model.well_casing_depth,
            "well_completion_date": model.well_completion_date,
            "well_driller_name": model.well_driller_name,
            "well_construction_method": model.well_construction_method,
            "well_pump_type": model.well_pump_type,
            "well_pump_depth": model.well_pump_depth,
            "formation_completion_code": model.formation_completion_code,
            "is_suitable_for_datalogger": model.is_suitable_for_datalogger,
        }
        if collection_id == "wells":
            properties["well_purposes"] = [
                purpose.purpose for purpose in (model.well_purposes or [])
            ]
            properties["well_casing_materials"] = [
                casing.material for casing in (model.well_casing_materials or [])
            ]
            properties["well_screens"] = [
                {
                    "screen_depth_top": screen.screen_depth_top,
                    "screen_depth_bottom": screen.screen_depth_bottom,
                    "screen_type": screen.screen_type,
                    "screen_description": screen.screen_description,
                }
                for screen in (model.screens or [])
            ]
        if hasattr(model, "nma_formation_zone"):
            properties["nma_formation_zone"] = model.nma_formation_zone
    return {
        "type": "Feature",
        "id": model.id,
        "geometry": geometry,
        "properties": _json_ready(properties),
    }


def _safe_json(value: str) -> dict[str, Any]:
    try:
        return __import__("json").loads(value)
    except Exception:
        return {}


def _json_ready(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(val) for val in value]
    return value


def get_items(
    request: Request,
    session,
    collection_id: str,
    bbox: str | None,
    datetime_value: str | None,
    limit: int,
    offset: int,
    properties: str | None,
    filter_expr: str | None,
    filter_lang: str | None,
) -> dict[str, Any]:
    if collection_id == "locations":
        query = _location_query()
        column_map = {
            "id": Location.id,
            "description": Location.description,
            "county": Location.county,
            "state": Location.state,
            "quad_name": Location.quad_name,
            "release_status": Location.release_status,
        }
        datetime_column = Location.created_at
        relationship_map = {}
    elif collection_id == "wells":
        query = _thing_query("water well")
        column_map = {
            "id": Thing.id,
            "name": Thing.name,
            "thing_type": Thing.thing_type,
            "first_visit_date": Thing.first_visit_date,
            "nma_pk_welldata": Thing.nma_pk_welldata,
            "well_depth": Thing.well_depth,
            "hole_depth": Thing.hole_depth,
            "well_casing_diameter": Thing.well_casing_diameter,
            "well_casing_depth": Thing.well_casing_depth,
            "well_completion_date": Thing.well_completion_date,
            "well_driller_name": Thing.well_driller_name,
            "well_construction_method": Thing.well_construction_method,
            "well_pump_type": Thing.well_pump_type,
            "well_pump_depth": Thing.well_pump_depth,
            "formation_completion_code": Thing.formation_completion_code,
            "is_suitable_for_datalogger": Thing.is_suitable_for_datalogger,
        }
        if hasattr(Thing, "nma_formation_zone"):
            column_map["nma_formation_zone"] = Thing.nma_formation_zone
        datetime_column = Thing.created_at
        relationship_map = {
            "well_purposes": lambda values: exists(
                select(1).where(
                    WellPurpose.thing_id == Thing.id,
                    WellPurpose.purpose.in_(values),
                )
            ),
            "well_casing_materials": lambda values: exists(
                select(1).where(
                    WellCasingMaterial.thing_id == Thing.id,
                    WellCasingMaterial.material.in_(values),
                )
            ),
            "well_screen_type": lambda values: exists(
                select(1).where(
                    WellScreen.thing_id == Thing.id,
                    WellScreen.screen_type.in_(values),
                )
            ),
        }
    elif collection_id == "springs":
        query = _thing_query("spring")
        column_map = {
            "id": Thing.id,
            "name": Thing.name,
            "thing_type": Thing.thing_type,
            "nma_pk_welldata": Thing.nma_pk_welldata,
        }
        datetime_column = Thing.created_at
        relationship_map = {}
    else:
        raise HTTPException(status_code=404, detail="Collection not found")

    if bbox:
        query = _apply_bbox_filter(query, bbox)
    if datetime_value:
        query = _apply_datetime_filter(query, datetime_value, datetime_column)
    if properties:
        query = _apply_properties_filter(
            query, properties, column_map, relationship_map
        )
    if filter_expr:
        if filter_lang and filter_lang.lower() != "cql2-text":
            raise HTTPException(status_code=400, detail="Unsupported filter-lang")
        query = _apply_cql_filter(query, filter_expr)

    total = session.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar_one()
    rows = session.execute(query.limit(limit).offset(offset)).all()
    features = [_build_feature(row, collection_id) for row in rows]

    base = str(request.base_url).rstrip("/")
    links = [
        {
            "href": f"{base}/ogc/collections/{collection_id}/items?limit={limit}&offset={offset}",
            "rel": "self",
            "type": "application/geo+json",
        },
        {
            "href": f"{base}/ogc/collections/{collection_id}",
            "rel": "collection",
            "type": "application/json",
        },
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "links": links,
        "numberMatched": total,
        "numberReturned": len(features),
    }


def get_item(
    request: Request,
    session,
    collection_id: str,
    fid: int,
) -> dict[str, Any]:
    if collection_id == "locations":
        query = _location_query().where(Location.id == fid)
    elif collection_id == "wells":
        query = _thing_query("water well").where(Thing.id == fid)
    elif collection_id == "springs":
        query = _thing_query("spring").where(Thing.id == fid)
    else:
        raise HTTPException(status_code=404, detail="Collection not found")

    row = session.execute(query).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Feature not found")

    feature = _build_feature(row, collection_id)
    base = str(request.base_url).rstrip("/")
    feature["links"] = [
        {
            "href": f"{base}/ogc/collections/{collection_id}/items/{fid}",
            "rel": "self",
            "type": "application/geo+json",
        },
        {
            "href": f"{base}/ogc/collections/{collection_id}",
            "rel": "collection",
            "type": "application/json",
        },
    ]
    return feature
