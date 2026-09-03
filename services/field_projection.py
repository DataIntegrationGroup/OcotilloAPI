# ===============================================================================
# Copyright 2025 ross
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
services/field_projection.py

Loads ``core/field-allowlists.yml`` and turns a database row into the record an
audience actually receives.

This is the chokepoint from ADR5 A.2. Every published payload is built here, so
a new route or a new output format cannot skip the rule by omission -- it sits
below them. The rules themselves are in ``domain/field_projection.py``.

Two consumers, because there are two publication paths:

* ``services/visibility.py`` builds destination payloads from ORM rows and
  calls :func:`project_entity`.
* ``core/feature_provider.py`` serves the public OGC collections and calls
  :func:`ogc_allowlist` at provider construction, so the columns nobody
  approved are never selected from Postgres at all.

The whole file is validated the first time it is read: an unknown field name, a
transform on a field nobody publishes, or an allowlist naming a never-public
field raises. Failing at load rather than at request time is deliberate; the
alternative is discovering a typo by noticing data that should have been there,
or worse, data that should not have been.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from db.location import Location
from db.thing import Thing
from domain.field_projection import (
    EntityProjection,
    NeverPublicFieldAllowed,
    project,
    validate_projection,
)

CONFIG_PATH = Path(__file__).parent.parent / "core" / "field-allowlists.yml"

THING = "thing"
LOCATION = "location"

# Fields a projection may name, per entity. Model columns plus the derived
# values a payload carries instead of raw storage: `point` is a PostGIS
# geometry nobody consumes directly, so `latitude` and `longitude` stand in
# for it and can be rounded independently.
DERIVED_FIELDS = {
    THING: frozenset(),
    LOCATION: frozenset({"latitude", "longitude"}),
}
ENTITY_MODELS = {THING: Thing, LOCATION: Location}


def known_fields(entity: str) -> frozenset:
    model = ENTITY_MODELS[entity]
    columns = {column.name for column in model.__table__.columns}
    return frozenset(columns | DERIVED_FIELDS[entity])


@lru_cache(maxsize=1)
def _configuration(path: str = None) -> dict:
    """Parse and validate the allowlists once per process."""
    raw = yaml.safe_load(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))

    never_public = {
        entity: frozenset(fields or ())
        for entity, fields in (raw.get("never_public") or {}).items()
    }

    audiences = {}
    for keyed_by in ("by_kind", "by_slug"):
        for audience, entities in (
            (raw.get("audiences") or {}).get(keyed_by) or {}
        ).items():
            for entity, rule in (entities or {}).items():
                projection = _build_projection(entity, rule, never_public)
                audiences[(keyed_by, audience, entity)] = projection

    ogc = raw.get("ogc") or {}
    ogc_never = frozenset(ogc.get("never_public") or ())
    ogc_collections = {}
    for table, columns in (ogc.get("collections") or {}).items():
        columns = frozenset(columns or ())
        forbidden = sorted(columns & ogc_never)
        if forbidden:
            # The same rule as the audience allowlists: a never-public field
            # cannot be re-admitted by naming it somewhere else.
            raise NeverPublicFieldAllowed(
                f"{table}.{forbidden[0]} is on the OGC never-public list and "
                "cannot be published by a collection."
            )
        ogc_collections[table] = columns

    return {
        "never_public": never_public,
        "audiences": audiences,
        "ogc_never_public": ogc_never,
        "ogc_collections": ogc_collections,
    }


def _build_projection(entity: str, rule, never_public: dict) -> EntityProjection:
    if entity not in ENTITY_MODELS:
        raise KeyError(
            f"'{entity}' is not a projectable entity "
            f"({', '.join(sorted(ENTITY_MODELS))})."
        )

    # A bare list is the common case; the mapping form adds transforms.
    if isinstance(rule, list):
        fields, raw_transforms = rule, {}
    else:
        fields = (rule or {}).get("fields") or []
        raw_transforms = (rule or {}).get("transforms") or {}

    transforms = {}
    for field_name, spec in raw_transforms.items():
        # One transform per field: {"round": 2} -> ("round", 2).
        ((transform_name, argument),) = spec.items()
        transforms[field_name] = (transform_name, argument)

    validate_projection(
        entity=entity,
        fields=fields,
        transforms=transforms,
        known_fields=known_fields(entity),
        never_public=never_public.get(entity, frozenset()),
    )
    return EntityProjection(fields=frozenset(fields), transforms=transforms)


def projection_for(destination, entity: str) -> EntityProjection | None:
    """The rule for this destination, or None -- which means nothing is sent.

    A per-destination entry replaces its kind's rules rather than extending
    them, so what one audience receives is readable in one place.
    """
    configuration = _configuration()["audiences"]
    by_slug = configuration.get(("by_slug", destination.slug, entity))
    if by_slug is not None:
        return by_slug
    return configuration.get(("by_kind", destination.destination_kind, entity))


def never_public_fields(entity: str) -> frozenset:
    return _configuration()["never_public"].get(entity, frozenset())


# ============= OGC collections =============================================


def ogc_never_public() -> frozenset:
    """Fields no public OGC collection may publish."""
    return _configuration()["ogc_never_public"]


def ogc_allowlist(table: str) -> frozenset | None:
    """Columns this public collection publishes, or None if it is not one.

    None means "not projected" and covers the internal mount, whose tables are
    ``ogc_internal_*``. An empty frozenset means "listed nowhere", which is
    default deny: the collection publishes no properties until someone says
    what it may publish.
    """
    if table is None or table.startswith("ogc_internal_"):
        return None

    collections = _configuration()["ogc_collections"]
    if table not in collections:
        return frozenset()
    return collections[table]


def ogc_collection_tables() -> frozenset:
    """Every public table with an allowlist entry."""
    return frozenset(_configuration()["ogc_collections"])


def thing_record(thing) -> dict:
    """Every stored field of a thing, before projection."""
    return {
        column.name: getattr(thing, column.name)
        for column in Thing.__table__.columns
        if column.name != "search_vector"
    }


def location_record(location) -> dict:
    """Every stored field of a location, with the geometry as lat/lon."""
    record = {
        column.name: getattr(location, column.name)
        for column in Location.__table__.columns
        if column.name != "point"
    }
    latitude, longitude = location.latlon
    record["latitude"] = latitude
    record["longitude"] = longitude
    return record


def project_entity(destination, entity: str, record: dict) -> dict:
    """Apply this destination's rule to one record."""
    return project(
        record,
        projection_for(destination, entity),
        never_public=never_public_fields(entity),
    )


# ============= EOF =============================================
