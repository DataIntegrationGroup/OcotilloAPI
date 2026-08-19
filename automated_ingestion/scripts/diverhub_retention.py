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
Find how far back Diver-HUB actually serves each monitoring point.

This matters for two reasons.

``INITIAL_START`` is 2015-01-01, a floor chosen before anyone knew what the
vendor retains. A first run for a well with no history walks from there in
windows, and every window before the vendor's earliest reading is a request that
returns nothing -- against an endpoint that answers 500 when pushed.

And the fourteen wells that already hold AMPAPI data stop in August 2022, while
the vendor appears to start much later. If so the two datasets never overlap,
which is why the datum comparison found nothing to compare: there is a gap
between them, not a seam.

Binary search on presence, roughly ten requests per point rather than a walk.

    export DIVERHUB_USERNAME=... DIVERHUB_PASSWORD=...
    uv run --group ingestion python -m \\
        automated_ingestion.scripts.diverhub_retention --limit 6
"""

import argparse
from datetime import datetime, timedelta, timezone

PROBE_WINDOW = timedelta(days=30)


def _has_data(client, point_id: int, when: datetime, reference: int) -> bool:
    """Is there any reading in the month starting at ``when``?"""
    rows = client.water_levels(
        point_id,
        int(when.timestamp()),
        int((when + PROBE_WINDOW).timestamp()),
        reference=reference,
        span=int(PROBE_WINDOW.total_seconds()),
    )
    return any(True for _ in rows)


def earliest_reading(
    client, point_id: int, reference: int, floor: datetime
) -> datetime | None:
    """Approximate the first month that holds data, by bisection."""
    now = datetime.now(tz=timezone.utc)
    if not _has_data(client, point_id, now - PROBE_WINDOW, reference):
        # Nothing recent; the point may be retired. Fall back to a wide check.
        if not _has_data(client, point_id, floor, reference):
            pass  # keep searching regardless -- absence now proves nothing

    low, high = floor, now
    if _has_data(client, point_id, low, reference):
        return low

    # Invariant: no data at `low`, data somewhere at or before `high`.
    for _ in range(12):
        if (high - low) <= PROBE_WINDOW:
            break
        middle = low + (high - low) / 2
        if _has_data(client, point_id, middle, reference):
            high = middle
        else:
            low = middle
    return high if _has_data(client, point_id, high - PROBE_WINDOW, reference) else high


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=6, help="How many points to probe")
    parser.add_argument("--floor", default="2015-01-01T00:00:00+00:00")
    args = parser.parse_args()

    import requests

    from automated_ingestion.sources.san_acacia.client import (
        GROUND_SURFACE_REFERENCE,
        DiverHubClient,
    )
    from automated_ingestion.sources.san_acacia.dlt_pipeline import PROJECT_ID
    from domain.van_essen import parse_reading_timestamp

    client = DiverHubClient(requests.Session())
    floor = parse_reading_timestamp(args.floor)
    points = client.monitoring_points(PROJECT_ID)[: args.limit]

    print(f"Probing {len(points)} of {PROJECT_ID}'s monitoring points")
    print(f"  {'point':<12}{'earliest data (approx)':>26}")
    for point in points:
        found = earliest_reading(client, point["id"], GROUND_SURFACE_REFERENCE, floor)
        shown = found.date().isoformat() if found else "none found"
        print(f"  {point['name']:<12}{shown:>26}")

    print(
        "\nIf these cluster well after August 2022, the vendor and the existing\n"
        "AMPAPI records do not overlap, and INITIAL_START can be raised to the\n"
        "earliest date actually served -- saving a decade of empty requests on\n"
        "every first run."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ============= EOF =============================================
