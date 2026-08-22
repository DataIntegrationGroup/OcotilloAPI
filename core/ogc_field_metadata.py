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
"""Per-field prose for the OGC collections.

Collection-level ``title``/``description``/``keywords`` live in
``core/pygeoapi.py`` and the two pygeoapi config templates. This module is the
level below: what an individual column means, and what unit it is in.

The copy lives in ``core/ogc-field-descriptions.yml``, keyed by backing
relation name with the ``ogc_``/``ogc_internal_`` prefix stripped, so the
public and internal mounts share one entry per view.

Read ``docs/ogc-field-descriptions.md`` before changing the shape of the YAML
or upgrading pygeoapi.
"""

import json
import logging
from pathlib import Path

import yaml

LOGGER = logging.getLogger(__name__)

# The prefixes _thing_collections_block and _edr_collections_block prepend to a
# collection id to reach its backing relation. Longest first: "ogc_internal_"
# also starts with "ogc_".
TABLE_PREFIXES = ("ogc_internal_", "ogc_")

# Entries carry documentation, not schema. Types and formats stay with the
# provider's own reflection.
ALLOWED_KEYS = frozenset(
    {
        "title",
        "description",
        "x-ogc-unit",
        "x-ogc-unitLang",
        "x-ogc-propertySeq",
        # JSON Schema's own keyword. pygeoapi's HTML renders it as the schema
        # table's "Values" column, and its queryables handler emits it too.
        "enum",
        # Names a category in core/lexicon.json, expanded to `enum` on the way
        # out so a controlled vocabulary is not duplicated here.
        "enum-lexicon",
    }
)

DEFAULTS_KEY = "_defaults"

LEXICON_KEY = "enum-lexicon"

_CACHE = None
_LEXICON_CACHE = None


def _metadata_path() -> Path:
    return Path(__file__).resolve().parent / "ogc-field-descriptions.yml"


def _lexicon_path() -> Path:
    return Path(__file__).resolve().parent / "lexicon.json"


def lexicon_terms(category: str) -> list:
    """Terms in one core/lexicon.json category, in file order.

    The lexicon file seeds the database's controlled vocabularies, so reading
    it here keeps one source of truth for an enumerated column's valid values
    -- and keeps this module free of any database dependency.
    """
    global _LEXICON_CACHE
    if _LEXICON_CACHE is None:
        raw = json.loads(_lexicon_path().read_text(encoding="utf-8"))
        by_category: dict[str, list] = {}
        for term in raw.get("terms", []):
            for name in term.get("categories", []):
                by_category.setdefault(name, []).append(term["term"])
        _LEXICON_CACHE = by_category
    return list(_LEXICON_CACHE.get(category, []))


def _validate(raw: dict, path: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a mapping of table -> fields.")

    for table, fields in raw.items():
        if not isinstance(fields, dict):
            raise ValueError(f"{path}: {table} must be a mapping of field -> entry.")
        for field, entry in fields.items():
            if not isinstance(entry, dict):
                raise ValueError(
                    f"{path}: {table}.{field} must be a mapping, got {type(entry).__name__}."
                )
            if not entry.get("title"):
                raise ValueError(f"{path}: {table}.{field} is missing a title.")
            unknown = set(entry) - ALLOWED_KEYS
            if unknown:
                raise ValueError(
                    f"{path}: {table}.{field} has unsupported keys "
                    f"{sorted(unknown)}; allowed keys are {sorted(ALLOWED_KEYS)}."
                )
            values = entry.get("enum")
            if values is not None and (not isinstance(values, list) or not values):
                raise ValueError(
                    f"{path}: {table}.{field} enum must be a non-empty list."
                )
            category = entry.get(LEXICON_KEY)
            if category is not None and not lexicon_terms(category):
                raise ValueError(
                    f"{path}: {table}.{field} names lexicon category "
                    f"{category!r}, which has no terms in core/lexicon.json."
                )
    return raw


def load_field_metadata(refresh: bool = False) -> dict:
    """Return the parsed YAML, read once per process.

    Deliberately free of any database dependency: this is called during
    OpenAPI generation, which runs before the backing views need to exist.
    """
    global _CACHE
    if _CACHE is None or refresh:
        path = _metadata_path()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _CACHE = _validate(raw, path)
    return _CACHE


def strip_table_prefix(table: str) -> str:
    """Reduce ``ogc_water_wells``/``ogc_internal_water_wells`` to ``water_wells``."""
    for prefix in TABLE_PREFIXES:
        if table.startswith(prefix):
            return table[len(prefix) :]
    return table


def default_title(column_name: str) -> str:
    """Fallback title for a column with no entry: ``well_depth`` -> ``Well Depth``."""
    return column_name.replace("_", " ").strip().title()


def table_entries(table: str) -> dict:
    """Documentation entries in force for ``table``, defaults included."""
    metadata = load_field_metadata()
    entries = dict(metadata.get(DEFAULTS_KEY, {}))
    entries.update(metadata.get(strip_table_prefix(table), {}))
    return entries


def describe_fields(table: str, fields: dict) -> dict:
    """Annotate a provider's reflected ``fields`` with prose from the YAML.

    Returns a new dict of new per-field dicts. That is not tidiness:
    ``pygeoapi.api.get_collection_schema`` assigns the provider's own field
    dict into the response and then mutates it in place (pops ``format``,
    assigns ``x-ogc-role``), so handing out references into the cached YAML
    would let one request's mutations leak into the next one's.
    """
    entries = table_entries(table)
    described = {}
    undocumented = []

    for name, field in (fields or {}).items():
        annotated = dict(field)
        entry = entries.get(name)
        if entry:
            for key, value in entry.items():
                if key == LEXICON_KEY:
                    # Expanded here rather than stored, so the vocabulary stays
                    # defined in one place. An entry may still pin a literal
                    # `enum` instead when the column's values are set by the
                    # view's own SQL rather than by the lexicon.
                    annotated.setdefault("enum", lexicon_terms(value))
                    continue
                annotated[key] = value
        else:
            annotated.setdefault("title", default_title(name))
            undocumented.append(name)
        described[name] = annotated

    if undocumented:
        # Not fatal: a response with a generated title beats a 500. The drift
        # guard in tests/test_ogc_field_descriptions.py is what fails the build.
        LOGGER.warning(
            "No field description for %s.%s; falling back to a generated title.",
            table,
            ", ".join(sorted(undocumented)),
        )

    return described
