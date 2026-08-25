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
UTM zone/CRS lookup for a stored point, used on the read path.

``domain/wells.py`` parses a UTM zone label supplied on import, scoped to
AMP's CONUS-only water-well ingestion policy. This module is the read-side
counterpart and has no such scope: a ``Location`` can be stored anywhere on
earth, so this resolves the true WGS84 UTM zone for any point against
pyproj's CRS database rather than computing an EPSG code, and raises
``OutsideUtmDomain`` for the polar latitudes UTM doesn't cover. See
``schemas/location.py``.

Deliberately does not import ``AMP_UTM_ZONE_MIN/MAX`` or ``AMP_COORD_*``:
those are AMP ingestion policy, not a projection limit, and importing them
here is exactly the coupling that let a CONUS bound silently clamp this
worldwide path before.
"""

from functools import lru_cache

from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info

# UTM is undefined outside this band; polar points need UPS/Polar
# Stereographic (EPSG 32661/32761 or 3413/3031), which is not implemented
# here. Raising rather than clamping keeps that gap visible.
UTM_LAT_MIN, UTM_LAT_MAX = -80.0, 84.0


class OutsideUtmDomain(ValueError):
    """Raised when a point falls outside the latitude band UTM is defined for."""


def utm_zone_for_longitude(longitude: float) -> int:
    """
    Return the UTM zone number (1-60) for a longitude.

    UTM zones are 6 degrees wide starting at -180. The longitude is
    normalized onto [-180, 180) first so values at or past the antimeridian
    (180.0, 185, -190, ...) still land in range instead of returning 61, 62,
    or a negative zone.
    """
    return int(((longitude + 180) % 360) // 6) + 1


@lru_cache(maxsize=128)
def _utm_epsg(zone: int, northern: bool) -> int:
    """Look up the WGS84 UTM EPSG code for a zone/hemisphere pair."""
    # Resolved against the EPSG database rather than computed, so a zone that
    # doesn't exist raises instead of landing on an unrelated CRS.
    lon = (zone - 1) * 6 - 177  # zone central meridian
    lat = 1.0 if northern else -1.0
    suffix = f"{zone}{'N' if northern else 'S'}"
    for info in query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(lon, lat, lon, lat),
    ):
        if info.name.endswith(suffix):
            return int(info.code)
    raise OutsideUtmDomain(f"No WGS 84 UTM CRS for zone {suffix}")


def utm_crs_for_point(longitude: float, latitude: float) -> tuple[int, str]:
    """
    Return the ``(EPSG code, zone label)`` of the UTM zone containing a point.

    Hemisphere is derived from latitude, not assumed, since this path serves
    points anywhere on earth (unlike the AMP importer, which only ever
    accepts northern-hemisphere zones by policy).
    """
    if not UTM_LAT_MIN <= latitude <= UTM_LAT_MAX:
        raise OutsideUtmDomain(
            f"Latitude {latitude} is outside the UTM domain "
            f"({UTM_LAT_MIN} to {UTM_LAT_MAX}); polar points need UPS."
        )
    zone = utm_zone_for_longitude(longitude)
    northern = latitude >= 0
    return _utm_epsg(zone, northern), f"{zone}{'N' if northern else 'S'}"


# ============= EOF =============================================
