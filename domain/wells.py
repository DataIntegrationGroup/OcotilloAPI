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
Well rules used when importing the well inventory spreadsheet.

Every function here takes plain values and returns plain values, so the rules can
be exercised without a database. ``services/well_inventory_csv.py`` supplies the
values from a validated ``WellInventoryRow`` and persists whatever comes back.

Errors subclass ``ValueError`` because the importer already treats a ``ValueError``
raised while handling a row as a per-row validation failure rather than an aborted
import.
"""

import re

from core.constants import AMP_UTM_ZONE_MAX, AMP_UTM_ZONE_MIN, SRID_NAD83_UTM_BASE
from domain.units import convert_ft_to_m
from domain.values import enum_value

AUTOGEN_DEFAULT_PREFIX = "NM-"
AUTOGEN_PREFIX_REGEX = re.compile(r"^[A-Z]{2,3}-$", re.IGNORECASE)
AUTOGEN_TOKEN_REGEX = re.compile(
    r"^(?P<prefix>[A-Z]{2,3})\s*-\s*(?:x{4}|X{4})$", re.IGNORECASE
)

UTM_ZONE_REGEX = re.compile(r"^\s*(\d{1,2})\s*N\s*$", re.IGNORECASE)

RELEASE_STATUS_PUBLIC = "public"
RELEASE_STATUS_PRIVATE = "private"
RELEASE_STATUS_DRAFT = "draft"

UNKNOWN_DEPTH_SOURCE = "unknown"

SITE_NAME_ORGANIZATION = "NMBGMR"
OSE_WELL_RECORD_ORGANIZATION = "NMOSE"
ALTERNATE_ID_RELATION = "same_as"


class UnsupportedUtmZone(ValueError):
    """Raised when a row carries a UTM zone the importer cannot project from."""


class ConflictingMeasuringPointHeight(ValueError):
    """Raised when a row gives two different measuring point heights."""


def autogen_prefix(well_id: str | None) -> str | None:
    """
    Return the normalized auto-generation prefix for a placeholder well id.

    Returns ``None`` when the value is a real well id and should be used as-is.

    Supported placeholder forms:

    - ``XY-`` / ``ABC-`` -- a bare 2-3 letter prefix
    - ``WL-XXXX`` / ``SAC-xxxx`` -- a prefix with a placeholder number, with
      optional spaces around the dash
    - blank -- uses the default ``NM-`` prefix
    """
    value = (well_id or "").strip()

    if not value:
        return AUTOGEN_DEFAULT_PREFIX

    if AUTOGEN_PREFIX_REGEX.match(value):
        return f"{value[:-1].upper()}-"

    match = AUTOGEN_TOKEN_REGEX.match(value)
    if match:
        return f"{match.group('prefix').upper()}-"

    return None


def utm_zone_number(utm_zone: str | None) -> int:
    """
    Parse a UTM zone label (e.g. ``"13N"``) into its zone number.

    Accepts any northern-hemisphere zone from ``AMP_UTM_ZONE_MIN`` to
    ``AMP_UTM_ZONE_MAX`` (10N-19N spans the continental US), case-insensitively
    and tolerant of surrounding whitespace. This is AMP water-well ingestion
    policy, not a projection limit -- see domain/geospatial.py for the
    worldwide read path. Anything else -- a bad shape, a southern-hemisphere
    suffix, or a zone outside that range -- raises ``UnsupportedUtmZone``.
    """
    match = UTM_ZONE_REGEX.match(utm_zone or "")
    if match:
        zone = int(match.group(1))
        if AMP_UTM_ZONE_MIN <= zone <= AMP_UTM_ZONE_MAX:
            return zone

    raise UnsupportedUtmZone(
        f"Unsupported UTM zone: {utm_zone}. AMP well submissions are limited "
        f"to CONUS zones {AMP_UTM_ZONE_MIN}N-{AMP_UTM_ZONE_MAX}N "
        f"(southern-hemisphere zones are not accepted)."
    )


def srid_for_utm_zone(utm_zone: str | None) -> int:
    """Return the EPSG code for a supported UTM zone label."""
    return SRID_NAD83_UTM_BASE + utm_zone_number(utm_zone)


def elevation_m_from_ft(elevation_ft: float | str | None) -> float:
    """
    Convert a reported elevation to the meters the ``Location`` row stores.

    A missing elevation becomes ``0.0`` rather than ``NULL``: ``Location.elevation``
    is not nullable, and the inventory sheet leaves the column blank for wells
    whose elevation has not been surveyed yet.
    """
    if elevation_ft is None:
        return 0.0
    return convert_ft_to_m(float(elevation_ft))


def release_status(public_availability_acknowledgement: bool | None) -> str:
    """
    Map the public-availability acknowledgement to a location release status.

    The acknowledgement is deliberately three-state. An unanswered question is
    not the same as a refusal, so it holds the location in ``draft`` instead of
    publishing or hiding it.
    """
    if public_availability_acknowledgement is True:
        return RELEASE_STATUS_PUBLIC
    if public_availability_acknowledgement is False:
        return RELEASE_STATUS_PRIVATE
    return RELEASE_STATUS_DRAFT


def resolve_measuring_point_height(
    mp_height: float | None,
    measuring_point_height_ft: float | None,
) -> float | None:
    """
    Reconcile the two columns that can carry a measuring point height.

    The sheet grew a second spelling of the same measurement. Either may be
    supplied, but when both are they must agree -- guessing which one is
    authoritative would silently bias every water level computed against it.
    """
    if (
        mp_height is not None
        and measuring_point_height_ft is not None
        and mp_height != measuring_point_height_ft
    ):
        raise ConflictingMeasuringPointHeight(
            "Conflicting values for measuring point height: "
            "mp_height and measuring_point_height_ft"
        )

    if measuring_point_height_ft is not None:
        return measuring_point_height_ft
    return mp_height


def historic_depth_to_water_source(depth_source) -> str:
    """
    Return the source to credit for a historic depth-to-water reading.

    Developer's note: Laila said the depth source is almost always the source for
    the historic depth to water, and that reusing it here is acceptable.
    """
    if not depth_source:
        return UNKNOWN_DEPTH_SOURCE
    return str(enum_value(depth_source)).lower()


def historic_depth_to_water_note(
    historic_depth_to_water_ft: float | None,
    depth_source,
) -> str | None:
    """
    Render the historic depth-to-water note, or ``None`` when there is no reading.

    The value is recorded as a note rather than a measurement because it is
    hearsay from the well owner, not something the field crew observed.
    """
    if historic_depth_to_water_ft is None:
        return None
    source = historic_depth_to_water_source(depth_source)
    return (
        f"historic depth to water: {historic_depth_to_water_ft} ft - source: {source}"
    )


def well_purposes(*purposes) -> list:
    """Collapse the fixed well-purpose columns into a list, dropping blanks."""
    return [purpose for purpose in purposes if purpose]


def alternate_ids(site_name: str | None, ose_well_record_id: str | None) -> list[dict]:
    """
    Build the alternate-id payloads for the identifiers other agencies use.

    ``thing_id`` is a placeholder; the caller replaces it once the ``Thing`` has
    been flushed and has an id.
    """
    pairs = (
        (site_name, SITE_NAME_ORGANIZATION),
        (ose_well_record_id, OSE_WELL_RECORD_ORGANIZATION),
    )
    return [
        {
            "thing_id": -1,
            "alternate_id": alternate_id,
            "alternate_organization": organization,
            "relation": ALTERNATE_ID_RELATION,
        }
        for alternate_id, organization in pairs
        if alternate_id is not None
    ]


# ============= EOF =============================================
