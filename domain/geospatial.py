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
UTM zone lookup for a stored point, used on the read path.

``domain/wells.py`` parses a UTM zone label supplied on import. This module is
the read-side counterpart: given a point already stored as WGS84, find the UTM
zone it actually falls in, so the GeoJSON response can report real coordinates
instead of a fixed zone. See ``schemas/location.py``.
"""

from core.constants import SRID_NAD83_UTM_BASE, UTM_ZONE_MAX, UTM_ZONE_MIN


def utm_zone_for_longitude(longitude: float) -> int:
    """
    Return the standard UTM zone number for a longitude, clamped to the
    continental US range this system supports (``UTM_ZONE_MIN..UTM_ZONE_MAX``).

    UTM zones are 6 degrees wide starting at -180 (zone 1 covers -180..-174).
    Clamping keeps the result inside the range EPSG defines as "NAD83 / UTM
    zone nN" (n = 1..23); above that, 269xx codes belong to unrelated NAD83
    state-plane systems, so an uncapped zone number could resolve to a valid
    but wrong CRS instead of failing loudly. Worldwide support is out of
    scope -- see domain/wells.py.
    """
    zone = int((longitude + 180) // 6) + 1
    return max(UTM_ZONE_MIN, min(UTM_ZONE_MAX, zone))


def srid_for_longitude(longitude: float) -> int:
    """Return the NAD83 UTM EPSG code for the zone a longitude falls in."""
    return SRID_NAD83_UTM_BASE + utm_zone_for_longitude(longitude)


# ============= EOF =============================================
