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
Which fields a set of data-type grants reaches (ADR5, Part III).

`permission_grant` says a principal may read "site metadata". `domain/access.py`
decides whether that grant covers a request. Neither knew what the sentence
meant in columns, so a data-type grant could be evaluated and never applied.
This module is that missing half: a classification of an entity's fields by
data type, and the projection that follows from it.

The rules, and why each is a rule rather than a convention:

* **Exhaustive.** Every field is classified or explicitly `always`. The
  alternative -- unlisted fields pass through -- means a column added next year
  is readable by everyone until somebody notices, which is the failure this
  layer exists to prevent.
* **Disjoint.** A field belongs to one data type. If two types could claim
  `well_depth`, revoking one would leave the field readable through the other,
  and "revoke well construction" would mean different things to different
  callers.
* **`always` is not grantable.** It carries the record's key, its release
  state, and its provenance -- what a row needs to be interpretable at all.
  There is no lexicon term for it and no grant can name it, so it cannot be
  revoked by accident. Gating provenance is a vocabulary decision, not a
  configuration one.

Default deny throughout: no data types means `always` and nothing else, which
is a record a caller can identify but learn nothing from.

Plain values only: dicts and sets in, dicts and sets out.
``services/field_projection.py`` reads the configuration and supplies them.
"""

from domain.field_projection import FieldProjectionError

ALWAYS = "always"


class UnclassifiedField(FieldProjectionError):
    """A field belongs to no data type and is not in `always`."""


class DuplicateFieldClassification(FieldProjectionError):
    """Two data types claim the same field."""


class UnknownDataType(FieldProjectionError):
    """A classification named a term that is not an access data type."""


def validate_classification(
    entity: str,
    always,
    by_data_type: dict,
    known_fields,
    known_data_types,
) -> None:
    """Reject a classification that could not be honored, before it is used.

    Raised at load rather than at request time, for the same reason the
    audience allowlists are: the symptom of a bad classification is data that
    quietly should or should not have been there.
    """
    unknown_types = sorted(set(by_data_type) - set(known_data_types))
    if unknown_types:
        raise UnknownDataType(
            f"'{unknown_types[0]}' is not an access data type "
            f"({', '.join(sorted(known_data_types))}). A classification under "
            "a term nobody can grant would never be applied."
        )

    seen = {}
    for data_type, fields in by_data_type.items():
        for field_name in fields:
            if field_name in seen:
                raise DuplicateFieldClassification(
                    f"{entity}.{field_name} is claimed by both "
                    f"'{seen[field_name]}' and '{data_type}'. A field belongs "
                    "to one data type, or revoking one type would not withhold "
                    "it."
                )
            seen[field_name] = data_type

    overlap = sorted(set(always) & set(seen))
    if overlap:
        raise DuplicateFieldClassification(
            f"{entity}.{overlap[0]} is in `always` and in "
            f"'{seen[overlap[0]]}'. `always` cannot be granted, so listing a "
            "field in both makes the grant meaningless."
        )

    classified = set(always) | set(seen)

    unknown = sorted(classified - set(known_fields))
    if unknown:
        raise UnclassifiedField(
            f"{entity} has no field(s) {', '.join(unknown)}. A classification "
            "naming a field that does not exist is a typo, and a typo here "
            "silently withholds data."
        )

    missing = sorted(set(known_fields) - classified)
    if missing:
        raise UnclassifiedField(
            f"{entity}.{missing[0]} belongs to no data type and is not in "
            "`always`. Every field is classified deliberately: a new column "
            "stops the process here rather than defaulting into visibility or "
            "into silence."
        )


def fields_for(always, by_data_type: dict, data_types) -> frozenset:
    """The fields these data types reach, plus what every reader gets.

    A caller holding several types gets the union: the types name different
    columns, so holding two is more than holding either.
    """
    reachable = set(always)
    for data_type in data_types or ():
        reachable |= set(by_data_type.get(data_type) or ())
    return frozenset(reachable)


def project_data_types(record: dict, allowed_fields) -> dict:
    """One record, as a caller holding these fields' data types receives it.

    Withheld fields are absent, not null: a null says "we looked and there is
    nothing", and that is a different sentence from "you may not see this".
    """
    return {
        field_name: value
        for field_name, value in record.items()
        if field_name in allowed_fields
    }


# ============= Response fields ==============================================
#
# A response is not its table: two thirds of WellResponse is derived from
# provenance rows, history tables and child collections. Those fields are
# resolved here, so a projection covers what a caller actually receives rather
# than only the columns underneath it.

WITHHELD = "withheld"


class UnclassifiedResponseField(FieldProjectionError):
    """A response declares a field no rule resolves."""


def _strip_suffix(name: str, suffixes) -> str | None:
    """The field `name` is built from, by the longest matching suffix."""
    matches = [suffix for suffix in suffixes if name.endswith(suffix)]
    if not matches:
        return None
    longest = max(matches, key=len)
    base = name[: -len(longest)]
    return base or None


def resolve_response_field(
    name: str,
    column_types: dict,
    response_types: dict,
    pending,
    suffixes,
    _seen: frozenset = frozenset(),
) -> str:
    """Which data type reaches this response field.

    Returns a data type, ``ALWAYS``, or ``WITHHELD``. Rules in order: it is a
    column; it is built from another field by a suffix; it is named. Recursion
    is what lets `measuring_point_height_unit` follow `measuring_point_height`,
    which is itself resolved by name -- a unit cannot outlive its value.
    """
    if name in column_types:
        return column_types[name]
    if name in response_types:
        return response_types[name]
    if name in pending:
        return WITHHELD

    base = _strip_suffix(name, suffixes)
    if base is not None and base not in _seen:
        return resolve_response_field(
            base,
            column_types,
            response_types,
            pending,
            suffixes,
            _seen | {name},
        )

    raise UnclassifiedResponseField(
        f"'{name}' is not a column, is built from no field, and is named by no "
        "data type. Classify it, or list it under "
        "`withheld_pending_classification` -- which withholds it from everyone "
        "and records the open question."
    )


def classify_response(
    schema_fields,
    column_types: dict,
    response_types: dict,
    pending,
    suffixes,
) -> dict:
    """Every field of one response, resolved to what reaches it."""
    return {
        name: resolve_response_field(
            name, column_types, response_types, pending, suffixes
        )
        for name in schema_fields
    }


def response_fields_for(classification: dict, data_types) -> frozenset:
    """Fields of this response a caller holding these data types receives.

    ``WITHHELD`` reaches nobody: an unanswered policy question is not a grant.
    """
    granted = set(data_types or ())
    return frozenset(
        name
        for name, data_type in classification.items()
        if data_type == ALWAYS or (data_type != WITHHELD and data_type in granted)
    )


# ============= EOF =============================================
