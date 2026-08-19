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
Check that ingested readings agree with the observations Ocotillo already holds.

Fourteen San Acacia wells carry AMPAPI transducer data through August 2022,
loaded under a datum nobody has verified. This pipeline reads Diver-HUB with
``reference=3`` and converts centimetres to feet. If those disagree, the same
series ends up holding two datums -- and the numbers look plausible either way,
which is the failure this source is most prone to.

Magnitude alone cannot settle it: ``reference=1`` (top of casing) differs from
``reference=3`` (ground surface) by a fixed 45.456 cm -- about 1.49 ft -- which
is well inside the natural range of these wells. Only values at the *same
instant* separate them, so this compares timestamp by timestamp.

It fetches all four references rather than just the one in use, so the output
also independently confirms which reference Ocotillo's existing data was loaded
against.

    export DIVERHUB_USERNAME=... DIVERHUB_PASSWORD=...
    uv run --group ingestion python -m \\
        automated_ingestion.scripts.compare_datum --well SO-0125

Read-only on both sides.
"""

import argparse
import statistics
import sys
from datetime import timedelta

REFERENCES = (0, 1, 2, 3)


def _existing(cursor, well: str, limit: int):
    cursor.execute(
        """
        SELECT o.observation_datetime, o.value
        FROM transducer_observation o
        JOIN deployment d ON d.id = o.deployment_id
        JOIN thing t ON t.id = d.thing_id
        WHERE t.name = %s
        ORDER BY o.observation_datetime DESC
        LIMIT %s
        """,
        (well, limit),
    )
    return cursor.fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--well", default="SO-0125", help="Ocotillo PointID")
    parser.add_argument("--point-id", type=int, help="Diver-HUB monitoring point id")
    parser.add_argument(
        "--instance", default="waterdatainitiative-271000:us-west4:dataservices"
    )
    parser.add_argument("--database", default="ocotillo-staging")
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument(
        "--tolerance-minutes",
        type=int,
        default=30,
        help=(
            "How far apart two readings may be and still count as the same "
            "instant. Exact equality is too strict: the existing rows are on the "
            "hour and the vendor logs at 15-minute offsets."
        ),
    )
    args = parser.parse_args()

    import requests
    from google.cloud.sql.connector import Connector

    from automated_ingestion.sources.san_acacia.client import DiverHubClient
    from automated_ingestion.sources.san_acacia.dlt_pipeline import PROJECT_ID
    from domain.units import convert_cm_to_ft
    from domain.van_essen import parse_reading_timestamp

    client = DiverHubClient(requests.Session())

    point_id = args.point_id
    if point_id is None:
        matches = [
            p for p in client.monitoring_points(PROJECT_ID) if p["name"] == args.well
        ]
        if not matches:
            print(f"{args.well} is not a Diver-HUB monitoring point.", file=sys.stderr)
            return 2
        point_id = matches[0]["id"]

    connector = Connector()
    conn = connector.connect(
        args.instance,
        "pg8000",
        user=_account(),
        db=args.database,
        enable_iam_auth=True,
    )
    try:
        rows = _existing(conn.cursor(), args.well, args.samples)
    finally:
        conn.close()
        connector.close()

    if not rows:
        print(f"No existing observations for {args.well}.", file=sys.stderr)
        return 1

    existing = {stamp.replace(tzinfo=None): value for stamp, value in rows}
    start = min(existing) - timedelta(days=1)
    end = max(existing) + timedelta(days=1)
    print(f"{args.well} (Diver-HUB point {point_id})")
    print(
        f"  {len(existing)} existing observations, {min(existing)} -> {max(existing)}"
    )
    print(
        f"  Ocotillo values: {min(existing.values()):.2f} .. {max(existing.values()):.2f} ft\n"
    )

    tolerance = timedelta(minutes=args.tolerance_minutes)
    print(
        f"  {'reference':<12}{'vendor rows':>12}{'matched':>9}"
        f"{'mean diff ft':>15}{'max diff ft':>14}"
    )
    best = None
    for reference in REFERENCES:
        vendor = {}
        for row in client.water_levels(
            point_id,
            int(start.timestamp()),
            int(end.timestamp()),
            reference=reference,
        ):
            if row.get("level") is None:
                continue
            stamp = parse_reading_timestamp(row["dateAndTime"]).replace(tzinfo=None)
            vendor[stamp] = convert_cm_to_ft(row["level"])

        # Nearest within tolerance rather than exact equality. A reading logged
        # at :45 against one recorded on the hour is the same measurement to
        # anyone comparing datums; insisting on identical timestamps finds
        # nothing and says nothing.
        stamps = sorted(vendor)
        diffs = []
        for stamp, value in existing.items():
            near = min(stamps, key=lambda s: abs(s - stamp)) if stamps else None
            if near is not None and abs(near - stamp) <= tolerance:
                diffs.append(abs(value - vendor[near]))

        if not diffs:
            print(f"  reference={reference:<4}{len(vendor):>10}{'none':>11}")
            continue

        mean, worst = statistics.mean(diffs), max(diffs)
        print(
            f"  reference={reference:<4}{len(vendor):>10}{len(diffs):>9}"
            f"{mean:>15.3f}{worst:>14.3f}"
        )
        if best is None or mean < best[1]:
            best = (reference, mean)

    if best is None:
        print("\n  Nothing to compare.")
        print(
            "  If vendor rows is 0, Diver-HUB does not retain this window for "
            "this point -- try a well whose data runs later, or widen --tolerance-minutes."
        )
        return 1

    reference, mean = best
    print(f"\n  Closest: reference={reference}, mean difference {mean:.3f} ft")
    if mean < 0.05:
        verdict = (
            f"Ocotillo's existing data matches reference={reference}."
            if reference == 3
            else f"Ocotillo's existing data was loaded on reference={reference}, NOT 3."
        )
    else:
        verdict = (
            "No reference matches closely. The existing data may use a different "
            "unit, datum or correction than any raw Diver-HUB series."
        )
    print(f"  {verdict}")
    return 0


def _account() -> str:
    import subprocess

    return subprocess.run(
        ["gcloud", "config", "get-value", "account"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())


# ============= EOF =============================================
