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
"""Well rules. No database, no fixtures."""

from enum import Enum

import pytest

from core.constants import SRID_NAD83_UTM_BASE
from domain.wells import (
    AUTOGEN_DEFAULT_PREFIX,
    ConflictingMeasuringPointHeight,
    UnsupportedUtmZone,
    alternate_ids,
    autogen_prefix,
    elevation_m_from_ft,
    historic_depth_to_water_note,
    historic_depth_to_water_source,
    release_status,
    resolve_measuring_point_height,
    srid_for_utm_zone,
    utm_zone_number,
    well_purposes,
)


class _DepthSource(Enum):
    DRILLER = "Driller"


# --------------------------------------------------------------------------
# autogen_prefix
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "well_id, expected",
    [
        ("", AUTOGEN_DEFAULT_PREFIX),
        ("   ", AUTOGEN_DEFAULT_PREFIX),
        (None, AUTOGEN_DEFAULT_PREFIX),
        ("XY-", "XY-"),
        ("xy-", "XY-"),
        ("ABC-", "ABC-"),
        ("WL-XXXX", "WL-"),
        ("SAC-xxxx", "SAC-"),
        ("WL - XXXX", "WL-"),
        ("  WL-XXXX  ", "WL-"),
    ],
)
def test_autogen_prefix_recognizes_placeholders(well_id, expected):
    assert autogen_prefix(well_id) == expected


@pytest.mark.parametrize(
    "well_id",
    ["AR0001", "WL-0001", "A-", "ABCD-", "WL-XXX", "WL-XXXXX", "NM-1234"],
)
def test_autogen_prefix_leaves_real_ids_alone(well_id):
    assert autogen_prefix(well_id) is None


# --------------------------------------------------------------------------
# srid_for_utm_zone / utm_zone_number
# --------------------------------------------------------------------------
@pytest.mark.parametrize("zone_number", range(10, 20))
def test_srid_for_utm_zone_maps_conus_zones(zone_number):
    assert srid_for_utm_zone(f"{zone_number}N") == SRID_NAD83_UTM_BASE + zone_number


@pytest.mark.parametrize(
    "zone, expected",
    [
        ("13N", 13),
        ("13n", 13),  # case-insensitive
        (" 13N ", 13),  # tolerant of surrounding whitespace
        ("10N", 10),
        ("19N", 19),
    ],
)
def test_utm_zone_number_normalizes_supported_zones(zone, expected):
    assert utm_zone_number(zone) == expected


@pytest.mark.parametrize("zone", ["9N", "20N", "13S", "", None, "13"])
def test_srid_for_utm_zone_rejects_unsupported_zones(zone):
    with pytest.raises(UnsupportedUtmZone, match=f"Unsupported UTM zone: {zone}"):
        srid_for_utm_zone(zone)


def test_unsupported_utm_zone_is_a_value_error():
    # The importer catches ValueError to fail a single row rather than the run.
    assert issubclass(UnsupportedUtmZone, ValueError)


# --------------------------------------------------------------------------
# elevation_m_from_ft
# --------------------------------------------------------------------------
def test_elevation_m_from_ft_converts():
    assert elevation_m_from_ft(10) == 3.048
    assert elevation_m_from_ft("10") == 3.048


def test_elevation_m_from_ft_defaults_missing_to_zero():
    # Location.elevation is not nullable and the sheet leaves it blank.
    assert elevation_m_from_ft(None) == 0.0


# --------------------------------------------------------------------------
# release_status
# --------------------------------------------------------------------------
def test_release_status_is_three_state():
    assert release_status(True) == "public"
    assert release_status(False) == "private"
    assert release_status(None) == "draft"


# --------------------------------------------------------------------------
# resolve_measuring_point_height
# --------------------------------------------------------------------------
def test_resolve_measuring_point_height_prefers_the_explicit_ft_column():
    assert resolve_measuring_point_height(None, 2.5) == 2.5
    assert resolve_measuring_point_height(2.5, 2.5) == 2.5


def test_resolve_measuring_point_height_falls_back_to_mp_height():
    assert resolve_measuring_point_height(1.5, None) == 1.5


def test_resolve_measuring_point_height_allows_both_missing():
    assert resolve_measuring_point_height(None, None) is None


def test_resolve_measuring_point_height_rejects_disagreement():
    with pytest.raises(ConflictingMeasuringPointHeight) as exc:
        resolve_measuring_point_height(1.5, 2.5)

    assert str(exc.value) == (
        "Conflicting values for measuring point height: "
        "mp_height and measuring_point_height_ft"
    )


def test_conflicting_measuring_point_height_is_a_value_error():
    assert issubclass(ConflictingMeasuringPointHeight, ValueError)


def test_resolve_measuring_point_height_accepts_a_shared_zero():
    # 0.0 is a real height, not a missing one.
    assert resolve_measuring_point_height(0.0, 0.0) == 0.0


# --------------------------------------------------------------------------
# historic depth to water
# --------------------------------------------------------------------------
def test_historic_depth_to_water_source_lowercases_an_enum():
    assert historic_depth_to_water_source(_DepthSource.DRILLER) == "driller"


def test_historic_depth_to_water_source_lowercases_a_string():
    assert historic_depth_to_water_source("Driller") == "driller"


@pytest.mark.parametrize("depth_source", [None, ""])
def test_historic_depth_to_water_source_defaults_to_unknown(depth_source):
    assert historic_depth_to_water_source(depth_source) == "unknown"


def test_historic_depth_to_water_note_renders_value_and_source():
    assert (
        historic_depth_to_water_note(42.5, _DepthSource.DRILLER)
        == "historic depth to water: 42.5 ft - source: driller"
    )


def test_historic_depth_to_water_note_is_none_without_a_reading():
    assert historic_depth_to_water_note(None, _DepthSource.DRILLER) is None


# --------------------------------------------------------------------------
# well_purposes / alternate_ids
# --------------------------------------------------------------------------
def test_well_purposes_drops_blanks_and_keeps_order():
    assert well_purposes("Monitoring", "Domestic") == ["Monitoring", "Domestic"]
    assert well_purposes("Monitoring", None) == ["Monitoring"]
    assert well_purposes(None, "Domestic") == ["Domestic"]
    assert well_purposes(None, None) == []


def test_alternate_ids_credits_the_right_organization():
    assert alternate_ids("SITE-1", "OSE-9") == [
        {
            "thing_id": -1,
            "alternate_id": "SITE-1",
            "alternate_organization": "NMBGMR",
            "relation": "same_as",
        },
        {
            "thing_id": -1,
            "alternate_id": "OSE-9",
            "alternate_organization": "NMOSE",
            "relation": "same_as",
        },
    ]


def test_alternate_ids_skips_missing_identifiers():
    assert alternate_ids(None, None) == []
    assert [
        entry["alternate_organization"] for entry in alternate_ids(None, "OSE-9")
    ] == ["NMOSE"]


# ============= EOF =============================================
