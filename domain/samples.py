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
"""Sample naming rules."""

from datetime import datetime

WATER_LEVEL_SAMPLE_TOKEN = "WL"
WATER_LEVEL_SAMPLE_TIMESTAMP_FORMAT = "%Y%m%d%H%M"


def water_level_sample_name(well_name: str, measured_at: datetime) -> str:
    """
    Build the deterministic sample identifier for a groundwater-level measurement.

    Both CSV importers use this name to decide whether a measurement has already
    been imported, so the two must agree exactly: the well inventory importer
    writes the name and later looks a well up by it, while the water level
    importer matches on it to update in place instead of inserting a duplicate.
    A drift between the two formats would silently turn every re-import into a
    new sample.
    """
    stamp = measured_at.strftime(WATER_LEVEL_SAMPLE_TIMESTAMP_FORMAT)
    return f"{well_name}-{WATER_LEVEL_SAMPLE_TOKEN}-{stamp}"


# ============= EOF =============================================
