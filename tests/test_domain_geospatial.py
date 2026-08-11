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
"""Read-side UTM zone lookup. No database, no fixtures."""

import pytest

from core.constants import SRID_NAD83_UTM_BASE
from domain.geospatial import srid_for_longitude, utm_zone_for_longitude


@pytest.mark.parametrize(
    "longitude, expected_zone",
    [
        (-105.0, 13),  # Albuquerque-ish, NM's eastern half
        (-107.949533, 13),
        (-109.05, 12),  # just west of NM's western border
        (-117.0, 11),  # Nevada
        (-69.0, 19),  # Maine, top of the CONUS range
        (-123.0, 10),  # Pacific coast, bottom of the CONUS range
    ],
)
def test_utm_zone_for_longitude_matches_the_true_zone(longitude, expected_zone):
    assert utm_zone_for_longitude(longitude) == expected_zone


@pytest.mark.parametrize(
    "longitude, expected_zone",
    [
        (-170.0, 10),  # far west of CONUS -- clamps rather than picking zone 3
        (170.0, 19),  # far east of CONUS -- clamps rather than picking zone 51
    ],
)
def test_utm_zone_for_longitude_clamps_outside_conus(longitude, expected_zone):
    # Clamping avoids handing pyproj a 269xx code outside the "NAD83 / UTM
    # zone nN" series, where the number is reused for unrelated state-plane
    # systems (see domain/geospatial.py).
    assert utm_zone_for_longitude(longitude) == expected_zone


def test_srid_for_longitude_derives_from_the_zone():
    assert srid_for_longitude(-105.0) == SRID_NAD83_UTM_BASE + 13
    assert srid_for_longitude(-117.0) == SRID_NAD83_UTM_BASE + 11


# ============= EOF =============================================
