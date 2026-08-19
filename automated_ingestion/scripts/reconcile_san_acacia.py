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
Produce the San Acacia reconciliation report.

Task 3.2 calls for this **before** anything is written: for each monitoring
point Diver-HUB returns, whether a matching Ocotillo well exists. Read-only on
both sides -- it fetches the vendor's point list and queries `thing`, and
changes nothing.

    export DIVERHUB_USERNAME=... DIVERHUB_PASSWORD=...
    uv run --group ingestion python -m \\
        automated_ingestion.scripts.reconcile_san_acacia

Exits non-zero when any point needs a human, so it can gate a later step
without anyone having to read the output carefully.
"""

import sys

from automated_ingestion.sources.san_acacia.reconcile import (
    ThingCandidate,
    VendorPoint,
    format_report,
    reconcile,
)


def _vendor_points() -> list[VendorPoint]:
    import requests

    from automated_ingestion.sources.san_acacia.client import DiverHubClient
    from automated_ingestion.sources.san_acacia.dlt_pipeline import PROJECT_ID

    client = DiverHubClient(requests.Session())
    return [
        VendorPoint(monitoring_point_id=p["id"], name=p["name"])
        for p in client.monitoring_points(PROJECT_ID)
    ]


def _candidates(prefix: str) -> list[ThingCandidate]:
    """Wells that could plausibly be San Acacia points.

    Narrowed by name prefix rather than loading every well: the point ids are
    `SO-####`, and comparing 38 names against the whole inventory would surface
    coincidental matches from other prefixes without adding a real one.
    """
    from sqlalchemy import select

    from db.engine import session_ctx
    from db.thing import Thing, ThingIdLink

    with session_ctx() as session:
        things = session.execute(
            select(Thing.id, Thing.name).where(Thing.name.ilike(f"{prefix}%"))
        ).all()
        links = session.execute(
            select(ThingIdLink.thing_id, ThingIdLink.alternate_id)
        ).all()

    by_thing: dict[int, list[str]] = {}
    for thing_id, alternate_id in links:
        if alternate_id:
            by_thing.setdefault(thing_id, []).append(alternate_id)

    return [
        ThingCandidate(
            thing_id=thing_id,
            name=name,
            external_ids=tuple(by_thing.get(thing_id, ())),
        )
        for thing_id, name in things
    ]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix",
        default="SO-",
        help="Well name prefix to consider as candidates (default: SO-).",
    )
    args = parser.parse_args()

    try:
        points = _vendor_points()
    except Exception as exc:  # noqa: BLE001 - the message is the useful part
        print(f"Could not list monitoring points: {exc}", file=sys.stderr)
        return 2

    candidates = _candidates(args.prefix)
    print(f"Vendor points from Diver-HUB : {len(points)}")
    print(f"Ocotillo wells named {args.prefix}*     : {len(candidates)}\n")

    report = reconcile(points, candidates)
    print(format_report(report))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())


# ============= EOF =============================================
