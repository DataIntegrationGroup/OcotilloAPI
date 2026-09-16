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

# EPSG 269xx == NAD83 / UTM zone xxN, but only for xx = 01..23; 26924-26928
# don't exist, and 26929+ names unrelated NAD83 state-plane systems. Safe here
# because AMP's 10N-19N range sits well inside 1-23.
SRID_NAD83_UTM_BASE = 26900

# AMP water-well ingestion policy: submissions are limited to the continental
# US. Not a projection limit -- domain/geospatial.py serves Location points
# stored anywhere on earth and must not import these; that coupling is what
# let a CONUS bound apply to the worldwide read path once before.
AMP_UTM_ZONE_MIN = 10
AMP_UTM_ZONE_MAX = 19

# A coarse sanity range, not a national border: it catches transposed
# easting/northing and feet-vs-meters entry mistakes on AMP well submissions.
# It is CONUS-shaped, not global -- e.g. it excludes the entire eastern
# hemisphere -- which is fine for this policy but wrong for anything else.
AMP_COORD_LAT_MIN, AMP_COORD_LAT_MAX = 18.0, 72.0
AMP_COORD_LON_MIN, AMP_COORD_LON_MAX = -180.0, -66.0

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
