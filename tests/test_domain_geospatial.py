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
"""Read-side UTM zone/CRS lookup. No database, no fixtures."""

import pytest

from domain.geospatial import (
    OutsideUtmDomain,
    utm_crs_for_point,
    utm_zone_for_longitude,
)


@pytest.mark.parametrize(
    "longitude, expected_zone",
    [
        (-105.0, 13),  # Albuquerque-ish, NM's eastern half
        (-107.949533, 13),
        (-109.05, 12),  # just west of NM's western border
        (-117.0, 11),  # Nevada
        (13.4, 33),  # Berlin
        (139.7, 54),  # Tokyo
    ],
)
def test_utm_zone_for_longitude_matches_the_true_zone(longitude, expected_zone):
    assert utm_zone_for_longitude(longitude) == expected_zone


@pytest.mark.parametrize(
    "longitude, expected_zone",
    [
        (180.0, 1),  # antimeridian
        (185.0, 1),  # past the antimeridian, unnormalized
        (-180.0, 1),
        (-190.0, 59),  # past -180, unnormalized
        (179.999, 60),
    ],
)
def test_utm_zone_for_longitude_normalizes_out_of_range_input(longitude, expected_zone):
    # int((lon + 180) // 6) + 1 alone returns 61/62/-1/-2 for these -- clamping
    # used to hide it. Normalizing onto [-180, 180) first fixes it at the root.
    assert utm_zone_for_longitude(longitude) == expected_zone


def test_utm_crs_for_point_resolves_northern_hemisphere():
    srid, zone_label = utm_crs_for_point(-105.0, 35.0)
    assert (srid, zone_label) == (32613, "13N")


def test_utm_crs_for_point_resolves_southern_hemisphere():
    # Buenos Aires-ish. Hemisphere can only come from latitude.
    srid, zone_label = utm_crs_for_point(-58.4, -34.6)
    assert (srid, zone_label) == (32721, "21S")


def test_utm_crs_for_point_resolves_southern_hemisphere_pacific():
    # Sydney-ish.
    srid, zone_label = utm_crs_for_point(151.2, -33.9)
    assert (srid, zone_label) == (32756, "56S")


@pytest.mark.parametrize("latitude", [84.0, -80.0])
def test_utm_crs_for_point_accepts_the_domain_edges(latitude):
    utm_crs_for_point(-105.0, latitude)  # must not raise


@pytest.mark.parametrize("latitude", [84.1, -80.1, 90.0, -90.0])
def test_utm_crs_for_point_rejects_outside_the_latitude_domain(latitude):
    with pytest.raises(OutsideUtmDomain, match="outside the UTM domain"):
        utm_crs_for_point(-105.0, latitude)


def test_outside_utm_domain_is_a_value_error():
    assert issubclass(OutsideUtmDomain, ValueError)


# ============= EOF =============================================
