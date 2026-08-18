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
Answer the open questions in BDMS task 2.1 against the live Diver-HUB API.

Run once, with credentials, and fold the output into
``docs/sources/san_acacia.md``. It reads and never writes.

    export DIVERHUB_USERNAME=... DIVERHUB_PASSWORD=...
    uv run --group ingestion python -m automated_ingestion.scripts.probe_diverhub

What it settles:

* Which project holds San Acacia Reach, and whether it really has 33 points.
* **Which ``reference`` value is ground surface.** The swagger declares the enum
  as ``[0, 1, 2, 3]`` and says nothing else, so this prints a sample from each
  side by side. The ground-surface series is recognisable by magnitude and sign
  against a well whose depth to water is roughly known -- a judgement a person
  has to make, which is why this script prints rather than decides.
* The window ceiling. Three months is known good; this widens until the API
  answers 500, so the production span is measured rather than guessed.

Nothing here is imported by the pipeline. It is a one-off instrument.
"""

import sys
from datetime import datetime, timezone

from automated_ingestion.shared.windows import DAY
from automated_ingestion.sources.san_acacia.client import (
    DiverHubClient,
    DiverHubError,
)

REFERENCE_VALUES = (0, 1, 2, 3)


def _session():
    import requests

    return requests.Session()


def _iso(unix: int) -> str:
    return datetime.fromtimestamp(unix, tz=timezone.utc).isoformat()


def probe_projects(client: DiverHubClient) -> list[dict]:
    print("== Projects visible to these credentials ==")
    projects = client.projects()
    for project in projects:
        print(f"   {project['id']:>6}  {project['name']}")
    return projects


def probe_points(client: DiverHubClient, project_id: int) -> list[dict]:
    print(f"\n== Monitoring points in project {project_id} ==")
    points = client.monitoring_points(project_id)
    print(f"   {len(points)} points (the plan expects 33)")
    for point in points[:5]:
        print(f"   {point['id']:>6}  {point['name']}")
    if len(points) > 5:
        print(f"   ... and {len(points) - 5} more")
    return points


def probe_reference_values(client: DiverHubClient, point_id: int, end: int) -> None:
    """Sample each reference value so a human can tell which is ground surface."""
    print(f"\n== WaterLevelReference values for point {point_id} ==")
    print("   Ground surface should read as depth below ground: positive and")
    print("   plausible as feet-below-surface for this well. An elevation will")
    print("   look like a much larger number.\n")
    start = end - 30 * DAY
    for reference in REFERENCE_VALUES:
        try:
            rows = list(client.water_levels(point_id, start, end, reference=reference))
        except DiverHubError as exc:
            print(f"   reference={reference}: error -- {exc}")
            continue
        if not rows:
            print(f"   reference={reference}: no rows in the last 30 days")
            continue
        levels = [r["level"] for r in rows if r.get("level") is not None]
        sample = rows[0]
        print(
            f"   reference={reference}: {len(rows):>6} rows, "
            f"min={min(levels):.3f} max={max(levels):.3f} "
            f"first={sample.get('dateAndTime')} level={sample.get('level')}"
        )


def probe_window_ceiling(client: DiverHubClient, point_id: int, end: int) -> None:
    """Widen until the API breaks, so the production span is a measurement."""
    print(f"\n== Window ceiling for point {point_id} ==")
    for days in (90, 180, 365, 730, 1825):
        start = end - days * DAY
        try:
            rows = list(client.diver_data(point_id, start, end, span=days * DAY))
            print(f"   {days:>5}d ({_iso(start)}): ok, {len(rows)} rows")
        except DiverHubError as exc:
            print(f"   {days:>5}d: FAILED -- {exc}")
            print("   ^ ceiling is below this; use the last successful span.")
            return
    print("   No ceiling found up to 5 years.")


def main() -> int:
    try:
        client = DiverHubClient(_session())
    except DiverHubError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    end = int(datetime.now(tz=timezone.utc).timestamp())

    projects = probe_projects(client)
    if not projects:
        print("No projects visible; nothing further to probe.", file=sys.stderr)
        return 1

    project_id = projects[0]["id"]
    if len(projects) > 1:
        print(f"\n(using project {project_id}; pass another by editing this script)")

    points = probe_points(client, project_id)
    if not points:
        return 1

    point_id = points[0]["id"]
    probe_reference_values(client, point_id, end)
    probe_window_ceiling(client, point_id, end)

    print("\nRecord the findings in docs/sources/san_acacia.md and set")
    print("GROUND_SURFACE_REFERENCE in sources/san_acacia/client.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ============= EOF =============================================
