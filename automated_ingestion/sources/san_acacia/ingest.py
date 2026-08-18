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
Dagster assets for San Acacia.

Both assets land raw payloads in GCS and report what happened as metadata --
row counts, and for readings the number of points that failed. A run that
silently ingests nothing looks identical to a run with nothing to ingest, and
the metadata is what separates them.
"""

from datetime import datetime, timezone
from typing import Any

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from automated_ingestion.sources.san_acacia.client import DiverHubClient


def _client() -> DiverHubClient:
    import requests

    return DiverHubClient(requests.Session())


@asset(
    group_name="san_acacia",
    description="Monitoring point roster for the San Acacia project, landed raw.",
)
def raw_san_acacia_locations(context: AssetExecutionContext) -> Output[int]:
    """Land the point roster in the raw zone."""
    from automated_ingestion.sources.san_acacia.dlt_pipeline import (
        PROJECT_ID,
        build_pipeline,
        vanessen_locations,
    )

    client = _client()
    points = list(client.monitoring_points(PROJECT_ID))
    pipeline = build_pipeline(context.run.tags.get("environment", "staging"))
    pipeline.run(vanessen_locations(client))

    context.log.info("landed %s monitoring points", len(points))
    return Output(
        len(points),
        metadata={
            "monitoring_points": MetadataValue.int(len(points)),
            "project_id": MetadataValue.int(PROJECT_ID),
            "names": MetadataValue.text(", ".join(p["name"] for p in points[:10])),
        },
    )


@asset(
    group_name="san_acacia",
    deps=[raw_san_acacia_locations],
    description="Water level readings for every San Acacia point, landed raw.",
)
def raw_san_acacia_readings(context: AssetExecutionContext) -> Output[int]:
    """Land water levels for every point, isolating per-point failure."""
    from automated_ingestion.sources.san_acacia.dlt_pipeline import (
        PROJECT_ID,
        build_pipeline,
        vanessen_readings,
    )

    client = _client()
    points = [
        {"monitoring_point_id": p["id"], "name": p["name"]}
        for p in client.monitoring_points(PROJECT_ID)
    ]
    end = int(datetime.now(tz=timezone.utc).timestamp())

    pipeline = build_pipeline(context.run.tags.get("environment", "staging"))
    failures: list[dict[str, Any]] = []
    info = pipeline.run(vanessen_readings(client, points, end, failures))
    rows = _row_count(info)

    if failures:
        context.log.warning(
            "%s of %s points failed: %s",
            len(failures),
            len(points),
            ", ".join(str(f["monitoring_point_id"]) for f in failures),
        )

    return Output(
        rows,
        metadata={
            "rows_ingested": MetadataValue.int(rows),
            "points_attempted": MetadataValue.int(len(points)),
            "points_failed": MetadataValue.int(len(failures)),
            "failures": MetadataValue.json(failures),
        },
    )


def _row_count(load_info: Any) -> int:
    """Rows dlt reports as loaded, or 0 when it reports nothing."""
    try:
        return sum(
            metrics.get("rows_count", 0)
            for job in load_info.load_packages
            for metrics in getattr(job, "jobs", {}).values()
        )
    except Exception:  # noqa: BLE001 - metadata must never fail a good load
        return 0


# ============= EOF =============================================
