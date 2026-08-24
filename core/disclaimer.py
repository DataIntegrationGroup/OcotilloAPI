# ===============================================================================
# Copyright 2026
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
"""Canonical text of the Ocotillo data disclaimer.

The disclaimer is served at GET /disclaimer (api/disclaimer.py) and is the
target of `metadata.identification.terms_of_service` in both pygeoapi configs.
It lives here as plain constants rather than a template or a static file so
that the HTML and JSON renderings cannot drift apart, and so it ships with the
`core` package without any package-data wiring.
"""

DISCLAIMER_TITLE = "Disclaimer"

DISCLAIMER_CONTACT_EMAIL = "ocotillo-nmbg@nmt.edu"

DISCLAIMER_PARAGRAPHS: tuple[str, ...] = (
    "These geospatial data are shared to help the public understand New "
    "Mexico's geologic and water resources. All datasets have limitations, "
    "particularly when combining data collected at different times, scales, "
    "or for different purposes. Users should review the metadata for each "
    "dataset and verify conditions on-site before making legal, regulatory, "
    "or other high-consequence decisions. All geospatial datasets are "
    "inherently scale-dependent.",
    "The New Mexico Bureau of Geology and Mineral Resources (NMBGMR) provides "
    "these data 'as-is' without warranties. NMBGMR does not guarantee the "
    "accuracy, completeness, and timeliness of these data for any particular "
    "purpose. Conditions may have changed since the data were collected. "
    "Neither NMBGMR nor any partner agency providing data assumes liability "
    "for any errors, omissions, or consequences arising from the use or "
    "misuse of these data.",
    "References to specific products or companies do not imply endorsement. "
    "Proper citation of these data is appreciated. Questions or feedback: "
    f"{DISCLAIMER_CONTACT_EMAIL}",
)
