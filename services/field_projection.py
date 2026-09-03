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
from domain.data_type_fields import (
    ALWAYS,
    classify_response,
    fields_for,
    project_data_types,
    response_fields_for,
    validate_classification,
)
from domain.field_projection import (
    EntityProjection,
    NeverPublicFieldAllowed,
    project,
    validate_projection,
)

CONFIG_PATH = Path(__file__).parent.parent / "core" / "field-allowlists.yml"
DATA_TYPE_CONFIG_PATH = Path(__file__).parent.parent / "core" / "data-type-fields.yml"

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


# Columns that never reach a record, so nothing can classify or publish them.
# `search_vector` is a tsvector maintained for search; `point` is the PostGIS
# geometry `latitude`/`longitude` stand in for. Both are dropped by
# thing_record() and location_record() below, and the data-type classification
# is validated against what those produce rather than against raw columns.
NON_RECORD_FIELDS = {
    THING: frozenset({"search_vector"}),
    LOCATION: frozenset({"point"}),
}


def record_fields(entity: str) -> frozenset:
    """Fields a record of this entity actually carries."""
    return known_fields(entity) - NON_RECORD_FIELDS[entity]


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


# ============= Data-type classification ====================================
#
# The other axis. Everything above answers "what does this destination
# receive"; everything below answers "what does this data type cover", which is
# what makes a `permission_grant` naming a data type mean something on a read.


@lru_cache(maxsize=1)
def _data_type_configuration(path: str = None) -> dict:
    """Parse and validate core/data-type-fields.yml once per process.

    The access data types are read from the lexicon rather than hard-coded, so
    a classification cannot drift from the terms a grant may actually name.
    """
    from core.enums import AccessDataType

    raw = yaml.safe_load(
        Path(path or DATA_TYPE_CONFIG_PATH).read_text(encoding="utf-8")
    )
    known_data_types = frozenset(member.value for member in AccessDataType)

    configuration = {}
    for entity in ENTITY_MODELS:
        entry = (raw or {}).get(entity)
        if entry is None:
            raise KeyError(
                f"core/data-type-fields.yml classifies nothing for '{entity}'. "
                "Every projectable entity is classified, or a read of it could "
                "not be projected at all."
            )

        always = frozenset(entry.get(ALWAYS) or ())
        by_data_type = {
            data_type: frozenset(fields or ())
            for data_type, fields in entry.items()
            if data_type != ALWAYS
        }

        validate_classification(
            entity=entity,
            always=always,
            by_data_type=by_data_type,
            known_fields=record_fields(entity),
            known_data_types=known_data_types,
        )
        configuration[entity] = (always, by_data_type)

    return configuration


def data_type_fields(entity: str, data_types) -> frozenset:
    """Fields a caller holding these data types may read of this entity."""
    always, by_data_type = _data_type_configuration()[entity]
    return fields_for(always, by_data_type, data_types)


def data_types_covering(entity: str, field_name: str) -> str | None:
    """Which data type a field belongs to, or None when it is `always`.

    For the admin console and for explaining a withheld field, rather than for
    the projection itself.
    """
    _, by_data_type = _data_type_configuration()[entity]
    for data_type, fields in by_data_type.items():
        if field_name in fields:
            return data_type
    return None


def project_entity_for_data_types(entity: str, record: dict, data_types) -> dict:
    """One record, as a caller holding these data-type grants receives it.

    Default deny: no data types leaves `always` -- the key, the release state
    and the provenance -- and nothing else.
    """
    return project_data_types(record, data_type_fields(entity, data_types))


# ============= Response classification =====================================
#
# A response is not its table: two thirds of WellResponse comes from
# provenance rows, history tables and child collections. `responses` in
# core/data-type-fields.yml resolves those, so a projection covers what a
# caller receives rather than only the columns underneath it.

RESPONSE_SCHEMAS = "responses"


def _response_schema_models() -> dict:
    """Schemas under the classification, by name.

    Imported here rather than at module scope: `schemas` imports `db`, and this
    module is imported by `services.visibility`, which `schemas` must stay free
    of.
    """
    from schemas.thing import WellResponse

    return {"WellResponse": WellResponse}


@lru_cache(maxsize=1)
def _response_configuration() -> dict:
    """Resolve every field of every registered response, once per process.

    Validated at load like the column classification: a response field no rule
    reaches raises here rather than being quietly absent from a payload.
    """
    raw = yaml.safe_load(Path(DATA_TYPE_CONFIG_PATH).read_text(encoding="utf-8"))
    section = (raw or {}).get(RESPONSE_SCHEMAS) or {}

    suffixes = tuple(section.get("suffix_follows") or ())
    pending = frozenset(section.get("withheld_pending_classification") or ())
    response_types = {
        field_name: data_type
        for data_type, fields in (section.get("fields") or {}).items()
        for field_name in (fields or ())
    }

    # A response is built from an entity's columns, and `thing` is the only
    # entity with a response under the classification today.
    always, by_data_type = _data_type_configuration()[THING]
    column_types = {field_name: ALWAYS for field_name in always}
    for data_type, fields in by_data_type.items():
        for field_name in fields:
            column_types[field_name] = data_type

    models = _response_schema_models()
    configuration = {}
    for schema_name in section.get("schemas") or ():
        model = models.get(schema_name)
        if model is None:
            raise KeyError(
                f"core/data-type-fields.yml registers '{schema_name}', which "
                f"_response_schema_models() does not know "
                f"({', '.join(sorted(models))})."
            )
        configuration[schema_name] = classify_response(
            schema_fields=tuple(model.model_fields),
            column_types=column_types,
            response_types=response_types,
            pending=pending,
            suffixes=suffixes,
        )
    return configuration


def response_classification(schema_name: str) -> dict:
    """Every field of this response, mapped to what reaches it."""
    return _response_configuration()[schema_name]


def project_response_for_data_types(
    schema_name: str, payload: dict, data_types
) -> dict:
    """One response payload, as a caller holding these data types receives it.

    Withheld fields are absent rather than null, and a field pending
    classification is absent for everyone.
    """
    allowed = response_fields_for(response_classification(schema_name), data_types)
    return {name: value for name, value in payload.items() if name in allowed}


# ============= EOF =============================================
