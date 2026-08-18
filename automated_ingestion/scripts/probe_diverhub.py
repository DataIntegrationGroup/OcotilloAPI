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
    if len(points) != 33:
        print(
            "   ^ count differs from the plan; listing all so the extras\n         can be identified before anything is reconciled."
        )
        for point in points:
            print(f"      {point['id']:>6}  {point['name']}")
        return points
    for point in points[:5]:
        print(f"   {point['id']:>6}  {point['name']}")
    if len(points) > 5:
        print(f"   ... and {len(points) - 5} more")
    return points


def probe_reference_values(
    client: DiverHubClient, points: list[dict], end: int
) -> None:
    """Sample each reference value so a human can tell which is ground surface.

    Searches over a year, and moves on to another point if the first has gone
    quiet -- a diver that stopped reporting months ago tells us nothing about
    what the enum means.
    """
    print("\n== WaterLevelReference values ==")
    print("   Ground surface reads as depth below ground: positive, and")
    print("   plausible as feet below surface. An elevation is a much larger")
    print("   number. A vrd/TOC series looks like ground surface but is offset")
    print("   by the stickup, so compare against a well you know.\n")

    start = end - 365 * DAY
    for point in points[:6]:
        point_id, name = point["id"], point["name"]
        found = False
        for reference in REFERENCE_VALUES:
            try:
                rows = list(
                    client.water_levels(point_id, start, end, reference=reference)
                )
            except DiverHubError as exc:
                print(f"   {name} reference={reference}: error -- {exc}")
                continue
            if not rows:
                print(f"   {name} reference={reference}: no rows in 365d")
                continue
            found = True
            levels = [r["level"] for r in rows if r.get("level") is not None]
            print(
                f"   {name} reference={reference}: {len(rows):>5} rows, "
                f"min={min(levels):>10.3f} max={max(levels):>10.3f}  "
                f"first={rows[0].get('dateAndTime')} last={rows[-1].get('dateAndTime')}"
            )
        if found:
            print(f"\n   ^ compare these four for {name} and pick the datum.")
            return
    print("   No point returned water levels in the last year.")


def probe_window_ceiling(client: DiverHubClient, point_id: int, end: int) -> None:
    """Find what actually triggers a 500.

    Widening from the present tests span. Sliding a fixed narrow window back
    through time tests whether the failure is instead about *when* -- a range
    that predates the point's data. The two look identical from the status
    code, so both are worth separating here.
    """
    print(f"\n== Window behaviour for point {point_id} ==")
    print("   Widening back from now (tests span):")
    for days in (90, 180, 365, 545, 730):
        start = end - days * DAY
        try:
            rows = list(
                client.water_levels(
                    point_id,
                    start,
                    end,
                    reference=REFERENCE_VALUES[0],
                    span=days * DAY,
                )
            )
            print(f"     {days:>5}d: ok, {len(rows)} rows")
        except DiverHubError:
            print(f"     {days:>5}d: 500 even at the one-day floor")

    print("   Fixed 30-day window slid backwards (tests age, not span):")
    for years_back in (0, 1, 2, 3):
        window_end = end - years_back * 365 * DAY
        window_start = window_end - 30 * DAY
        label = f"{years_back}y ago"
        try:
            rows = list(
                client.water_levels(
                    point_id,
                    window_start,
                    window_end,
                    reference=REFERENCE_VALUES[0],
                    span=30 * DAY,
                )
            )
            print(f"     {label:>8}: ok, {len(rows)} rows")
        except DiverHubError:
            print(f"     {label:>8}: 500 at the floor")


def probe_datum_relationships(
    client: DiverHubClient, point_id: int, name: str, start: int, end: int
) -> None:
    """Settle what the four reference values mean, using the API against itself.

    Two questions the min/max summary cannot answer:

    1. **Is any of them an elevation rather than a depth?** An elevation moves
       opposite to a depth, so ``elevation + depth`` is constant while
       ``depth - depth`` is constant. Comparing aligned rows distinguishes them;
       comparing ranges does not, because both look like the same spread.
    2. **Which is ground surface?** ``ManualMeasurements`` reports
       ``waterLevelToc`` -- explicitly top of casing. Whichever reference tracks
       it *is* the TOC series, and ground surface is then the one shallower than
       it by the casing stickup.
    """
    print(f"\n== Datum relationships for {name} ==")
    series: dict[int, dict[str, float]] = {}
    for reference in REFERENCE_VALUES:
        rows = list(client.water_levels(point_id, start, end, reference=reference))
        series[reference] = {
            r["dateAndTime"]: r["level"] for r in rows if r.get("level") is not None
        }

    shared = set.intersection(*(set(v) for v in series.values())) if series else set()
    stamps = sorted(shared)[:3]
    if not stamps:
        print("   No overlapping timestamps across references.")
        return

    print("   Aligned samples:")
    print(f"     {'timestamp':<22}" + "".join(f"ref{r:<14}" for r in REFERENCE_VALUES))
    for stamp in stamps:
        cells = "".join(f"{series[r][stamp]:<17.3f}" for r in REFERENCE_VALUES)
        print(f"     {stamp:<22}{cells}")

    base = REFERENCE_VALUES[0]
    print(f"\n   Relationship to ref={base} across those samples:")
    for reference in REFERENCE_VALUES[1:]:
        diffs = {round(series[reference][t] - series[base][t], 3) for t in stamps}
        sums = {round(series[reference][t] + series[base][t], 3) for t in stamps}
        if len(diffs) == 1:
            print(
                f"     ref={reference}: constant OFFSET {diffs.pop():+.3f} "
                "-- same direction, so also a depth"
            )
        elif len(sums) == 1:
            print(
                f"     ref={reference}: constant SUM {sums.pop():.3f} "
                "-- INVERTED, so this one is an elevation"
            )
        else:
            print(f"     ref={reference}: neither constant; not a simple datum shift")

    print("\n   Manual measurements (waterLevelToc = top of casing):")
    try:
        manual = client.manual_measurements(point_id, start, end)
    except DiverHubError as exc:
        print(f"     unavailable -- {exc}")
        return
    if not manual:
        print("     none in this window; try a wider one.")
        return
    for record in manual[:3]:
        stamp = record.get("dateAndTime")
        toc = record.get("waterLevelToc")
        print(f"     {stamp}  toc={toc}")
        nearest = min(stamps, key=lambda t: abs(_epoch(t) - _epoch(stamp)))
        print(f"       nearest logged sample {nearest}:")
        for reference in REFERENCE_VALUES:
            delta = series[reference][nearest] - toc if toc is not None else None
            if delta is not None:
                print(
                    f"         ref={reference}: {series[reference][nearest]:.3f} "
                    f"(toc{delta:+.3f})"
                )
    print("\n   The reference nearest zero against toc IS the TOC series.")
    print("   Ground surface is shallower than TOC by the casing stickup.")


def _epoch(stamp: str) -> float:
    from datetime import datetime, timezone

    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


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
    probe_reference_values(client, points, end)
    probe_window_ceiling(client, point_id, end)
    probe_datum_relationships(client, point_id, points[0]["name"], end - 730 * DAY, end)

    print("\nRecord the findings in docs/sources/san_acacia.md and set")
    print("GROUND_SURFACE_REFERENCE in sources/san_acacia/client.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ============= EOF =============================================
