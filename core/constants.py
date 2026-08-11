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

SRID_WGS84 = 4326
SRID_UTM_ZONE_13N = 26913
SRID_UTM_ZONE_12N = 26912

# EPSG 269xx == NAD83 / UTM zone xxN. Zones 10N-19N span the continental US.
SRID_NAD83_UTM_BASE = 26900
UTM_ZONE_MIN = 10
UTM_ZONE_MAX = 19

# A coarse sanity range, not a national border: it catches transposed
# easting/northing and feet-vs-meters entry mistakes. It is wider than the US
# (e.g. it admits Mexico City) -- do not use it to decide "is this the US".
COORD_LAT_MIN, COORD_LAT_MAX = 18.0, 72.0
COORD_LON_MIN, COORD_LON_MAX = -180.0, -66.0

STATE_CODES = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
)
# ============= EOF =============================================
