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
Rules for turning Van Essen diver readings into Ocotillo values.

The vendor's Diver-HUB API reports water levels in centimetres against a datum
chosen by the request, and Ocotillo stores feet below ground surface. These
functions do that conversion and nothing else: no database, no HTTP, no vendor
client. The caller fetches; these rules decide what a fetched value means.

**What this mapping invents rather than reads**, since inventing is where a
mapping goes quietly wrong:

- *The datum.* The API does not say which datum a reading is on -- the request
  does. Every value here is assumed to have come from a request with
  ``reference=3``, established by measurement (see
  ``docs/sources/san_acacia.md``). A reading fetched with any other reference and
  passed through here is silently wrong, which is why the client has no default
  for that parameter.
- *The unit.* No field states it. Centimetres was inferred from the elevation
  reference resolving to San Acacia's ground elevation, and cross-checked
  against plausible depths for a riparian piezometer.
- *The timezone.* The API documents UTC but does not always mark it, so a naive
  timestamp is read as UTC rather than as local time.

**What it deliberately does not do.** Earlier drafts had this module converting
``drillingDepth`` from centimetres and building a WGS84 point from ``lat``/
``lng``. The live ``MonitoringPoint`` payload is ``{id, name}`` -- no depth, no
coordinates -- so those functions would have had no input. Well geometry and
construction come from the Ocotillo records a point reconciles against.

Errors subclass ``ValueError`` so a bad record is a per-row failure to the
caller, matching what the CSV importers already expect.
"""

import math
from datetime import datetime, timezone

from domain.units import convert_cm_to_ft

PROJECT_SLUG = "sanacaciareach"
"""Prefix for external identifiers. Matches the vendor's own ``uid`` form."""

MEASUREMENT_UNIT = "ft"
"""Ocotillo stores depth to water in feet."""

GROUND_SURFACE_REFERENCE = 3
"""The ``WaterLevelReference`` these rules assume a reading was fetched with.

Duplicated from the client deliberately: a rule that assumes a datum should
state which one, so that reading this module alone is enough to know what its
numbers mean.
"""


class VanEssenMappingError(ValueError):
    """A record cannot be mapped. Per-row, never fatal to a run."""


def parse_reading_timestamp(value: str) -> datetime:
    """Parse a Diver-HUB ``dateAndTime`` into a timezone-aware UTC datetime.

    A naive timestamp is read as UTC. Reading it as local time would shift every
    observation by the machine's offset -- and would do so differently on a
    developer's laptop and in a container, which is the kind of discrepancy that
    survives review.
    """
    if not isinstance(value, str) or not value.strip():
        raise VanEssenMappingError(f"Reading timestamp is missing or blank: {value!r}")

    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise VanEssenMappingError(
            f"Reading timestamp {value!r} is not an ISO-8601 instant."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def depth_to_water_ft(level_cm: float | None) -> float | None:
    """Convert a ground-surface reading in centimetres to feet.

    ``None`` passes through: the vendor reports gaps, and a gap is not an error.

    Negative values are kept. Depth below ground surface goes negative when
    water stands above ground, which happens in these riparian wells during high
    flow and is real data rather than a fault.
    """
    if level_cm is None:
        return None
    if isinstance(level_cm, bool) or not isinstance(level_cm, (int, float)):
        raise VanEssenMappingError(f"Reading level is not a number: {level_cm!r}")
    if math.isnan(level_cm) or math.isinf(level_cm):
        raise VanEssenMappingError(f"Reading level is not finite: {level_cm!r}")

    return convert_cm_to_ft(float(level_cm))


def external_point_key(monitoring_point_id: int) -> str:
    """Stable identifier for a monitoring point.

    Built from the vendor's numeric id rather than its name. Names like
    ``SO-0125`` are Bureau point ids and can be corrected; the numeric id is what
    the vendor's URLs use and is what a re-run has to resolve to the same record.
    """
    if isinstance(monitoring_point_id, bool) or not isinstance(
        monitoring_point_id, int
    ):
        raise VanEssenMappingError(
            f"Monitoring point id must be an integer: {monitoring_point_id!r}"
        )
    if monitoring_point_id <= 0:
        raise VanEssenMappingError(
            f"Monitoring point id must be positive: {monitoring_point_id!r}"
        )
    return f"{PROJECT_SLUG}-{monitoring_point_id}"


def external_series_key(monitoring_point_id: int) -> str:
    """Stable identifier for one point's depth-to-water series.

    A point could later carry more than one series -- temperature and
    conductivity are already in the vendor's raw payload -- so the datum is part
    of the key rather than implied by the point.
    """
    return f"{external_point_key(monitoring_point_id)}:dtw-gs"


# ============= EOF =============================================
