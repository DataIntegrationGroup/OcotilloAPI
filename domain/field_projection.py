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
Field projection: what an audience actually receives, field by field (ADR5, 3.5).

Record-level grants are not enough, because the Bureau's promises are
field-shaped. The owner's name and phone number sit on the same well record as
the water levels the owner agreed to share.

The rule is an allowlist, per audience:

* **Omission produces silence, not leakage.** Only fields explicitly approved
  for an audience appear in that audience's payload, so a column added next
  year is invisible until someone decides otherwise.
* **Protection includes transformation.** A public record can carry a
  coordinate rounded to protect the landowner while the precise value stays
  internal. Dropping the well from the map entirely is not the only option.
* **The never-public list wins over any allowlist.** Engineering guarantees a
  listed field is enforced everywhere; a named data owner decides what is on
  the list. A configuration that names one is a mistake, and it is raised at
  load rather than honored at request time.

Plain values only: dicts in, dicts out. ``services/field_projection.py`` reads
the configuration and supplies them.
"""

from dataclasses import dataclass, field as dataclass_field


class FieldProjectionError(ValueError):
    """Base for projection configuration problems."""


class NeverPublicFieldAllowed(FieldProjectionError):
    """An allowlist named a field no configuration may expose."""


class UnknownField(FieldProjectionError):
    """An allowlist named a field the entity does not have."""


class UnknownTransform(FieldProjectionError):
    """A transform nobody implements."""


@dataclass(frozen=True)
class EntityProjection:
    """The rule for one entity, for one audience."""

    fields: frozenset
    # field name -> (transform name, argument), e.g. "latitude" -> ("round", 2)
    transforms: dict = dataclass_field(default_factory=dict)


def round_to(value, places: int):
    """Reduce coordinate precision. Two decimal places is roughly a kilometre."""
    if value is None:
        return None
    return round(float(value), places)


# Transformations a configuration may ask for. Anything else raises at load,
# so a typo cannot silently degrade to "publish the value untouched".
TRANSFORMS = {"round": round_to}


def validate_projection(
    entity: str,
    fields,
    transforms: dict,
    known_fields,
    never_public,
) -> None:
    """Reject a projection that could not be honored, before it is used."""
    unknown = sorted(set(fields) - set(known_fields))
    if unknown:
        raise UnknownField(
            f"{entity} has no field(s) {', '.join(unknown)}. "
            "An allowlist naming a field that does not exist is a typo, and a "
            "typo in an allowlist silently withholds data."
        )

    forbidden = sorted(set(fields) & set(never_public))
    if forbidden:
        raise NeverPublicFieldAllowed(
            f"{entity}.{forbidden[0]} is on the never-public list and cannot "
            "be added to an audience. Removing it from that list is a policy "
            "decision with a named owner, not a configuration change."
        )

    for field_name, (transform_name, _) in transforms.items():
        if field_name not in fields:
            raise UnknownField(
                f"{entity}.{field_name} has a transform but is not in the "
                "allowlist, so the transform would never run."
            )
        if transform_name not in TRANSFORMS:
            raise UnknownTransform(
                f"'{transform_name}' is not a transform "
                f"({', '.join(sorted(TRANSFORMS))})."
            )


def project(record: dict, projection: EntityProjection, never_public=frozenset()):
    """One record, as this audience receives it.

    Default deny: an audience with no rule gets an empty dict, not the record.
    The never-public list is applied here as well as at load, so a field on it
    stays out even if a projection was built without validation.
    """
    if projection is None:
        return {}

    projected = {}
    for field_name, value in record.items():
        if field_name not in projection.fields:
            continue
        if field_name in never_public:
            continue

        transform = projection.transforms.get(field_name)
        if transform is not None:
            transform_name, argument = transform
            value = TRANSFORMS[transform_name](value, argument)

        projected[field_name] = value

    return projected


# ============= EOF =============================================
