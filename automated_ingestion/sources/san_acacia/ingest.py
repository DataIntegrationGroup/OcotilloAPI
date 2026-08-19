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

from automated_ingestion.defs.resources import OcotilloDatabase
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
        LOADER_FILE_FORMAT,
        PROJECT_ID,
        build_pipeline,
        vanessen_locations,
    )

    client = _client()
    points = list(client.monitoring_points(PROJECT_ID))
    pipeline = build_pipeline()
    pipeline.run(vanessen_locations(client), loader_file_format=LOADER_FILE_FORMAT)

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
        LOADER_FILE_FORMAT,
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

    pipeline = build_pipeline()
    failures: list[dict[str, Any]] = []
    info = pipeline.run(
        vanessen_readings(client, points, end, failures),
        loader_file_format=LOADER_FILE_FORMAT,
    )
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


@asset(
    group_name="san_acacia",
    deps=[raw_san_acacia_readings],
    description="Water levels mapped to the Ocotillo model and loaded to Postgres.",
)
def san_acacia_observations(
    context: AssetExecutionContext, database: OcotilloDatabase
) -> Output[int]:
    """Load San Acacia water levels into `transducer_observation`.

    Per well: match the vendor point to an Ocotillo well, choose the deployment
    its transducer hangs from, ask the database where that series got to, fetch
    forward from there, map, and upsert.

    A well that cannot be resolved is skipped and counted, never guessed at.
    Ingestion does not create wells or pick between candidate deployments, so an
    unresolved well is a question for a person -- and skipping it costs that
    well's readings for this run, not the other thirty-seven's.
    """
    from datetime import datetime, timezone

    from automated_ingestion.ocotillo.loader import ensure_block, load_observations
    from automated_ingestion.shared.watermark import (
        PostgresWatermarkStore,
        resolve_start,
    )
    from automated_ingestion.sources.san_acacia.adapter import SanAcaciaAdapter
    from automated_ingestion.sources.san_acacia.client import GROUND_SURFACE_REFERENCE
    from automated_ingestion.sources.san_acacia.dlt_pipeline import (
        INITIAL_START,
        PROJECT_ID,
        READING_SPAN,
    )
    from automated_ingestion.sources.san_acacia.reconcile import (
        VendorPoint,
        reconcile,
    )
    from automated_ingestion.sources.san_acacia.resolve import (
        PARAMETER_NAME,
        resolve_deployment,
    )
    from domain.van_essen import parse_reading_timestamp

    client = _client()
    points = [
        VendorPoint(monitoring_point_id=p["id"], name=p["name"])
        for p in client.monitoring_points(PROJECT_ID)
    ]
    end = int(datetime.now(tz=timezone.utc).timestamp())
    floor = parse_reading_timestamp(INITIAL_START)

    rows_loaded = 0
    skipped: list[dict[str, Any]] = []
    adapter_failures = 0

    with database.session() as session:
        parameter_id = _parameter_id(session, PARAMETER_NAME)
        report = reconcile(points, _well_candidates(session))
        watermarks = PostgresWatermarkStore(session)

        for match in report.matches:
            if match.needs_a_human:
                skipped.append({"point": match.point.name, "reason": match.kind.value})
                continue

            thing_id = match.thing_id
            resolution = resolve_deployment(_deployments(session, thing_id))
            if resolution.needs_a_human:
                skipped.append(
                    {"point": match.point.name, "reason": resolution.kind.value}
                )
                continue

            start = resolve_start(watermarks, thing_id, parameter_id, floor)
            adapter = SanAcaciaAdapter()
            raw = (
                {
                    "monitoring_point_id": match.point.monitoring_point_id,
                    "dateAndTime": row["dateAndTime"],
                    "level": row["level"],
                    "unit": "cm",
                    "reference": GROUND_SURFACE_REFERENCE,
                }
                for row in client.water_levels(
                    match.point.monitoring_point_id,
                    int(start.timestamp()),
                    end,
                    reference=GROUND_SURFACE_REFERENCE,
                    span=READING_SPAN,
                )
            )

            observations = list(adapter.to_observations(raw))
            adapter_failures += len(adapter.failures)
            if not observations:
                continue

            result = load_observations(
                session,
                observations,
                resolution.deployment_id,
                parameter_id,
                release_status="public",
            )
            rows_loaded += result.rows_written
            ensure_block(
                session,
                thing_id=thing_id,
                parameter_id=parameter_id,
                start=min(o.observation_datetime for o in observations),
                end=max(o.observation_datetime for o in observations),
                release_status="public",
            )

    if skipped:
        context.log.warning(
            "%s of %s wells skipped: %s",
            len(skipped),
            len(points),
            ", ".join(f"{s['point']} ({s['reason']})" for s in skipped),
        )

    return Output(
        rows_loaded,
        metadata={
            "rows_loaded": MetadataValue.int(rows_loaded),
            "wells_attempted": MetadataValue.int(len(points)),
            "wells_skipped": MetadataValue.int(len(skipped)),
            "adapter_failures": MetadataValue.int(adapter_failures),
            "skipped": MetadataValue.json(skipped),
        },
    )


def _parameter_id(session: Any, name: str) -> int:
    from sqlalchemy import select

    from db.parameter import Parameter

    parameter_id = session.scalar(
        select(Parameter.id).where(Parameter.parameter_name == name)
    )
    if parameter_id is None:
        raise RuntimeError(
            f"No parameter named {name!r}. Ingestion does not create parameters; "
            "seed it before loading."
        )
    return parameter_id


def _well_candidates(session: Any) -> list[Any]:
    """Ocotillo wells the vendor points might be, narrowed by name prefix."""
    from sqlalchemy import select

    from db.thing import Thing

    from automated_ingestion.sources.san_acacia.reconcile import ThingCandidate

    rows = session.execute(
        select(Thing.id, Thing.name).where(Thing.name.ilike("SO-%"))
    ).all()
    return [ThingCandidate(thing_id=i, name=n) for i, n in rows]


def _deployments(session: Any, thing_id: int) -> list[Any]:
    from sqlalchemy import select

    from db.deployment import Deployment
    from db.sensor import Sensor

    from automated_ingestion.sources.san_acacia.resolve import DeploymentCandidate

    rows = session.execute(
        select(Deployment.id, Sensor.sensor_type, Deployment.removal_date)
        .join(Sensor, Sensor.id == Deployment.sensor_id)
        .where(Deployment.thing_id == thing_id)
    ).all()
    return [
        DeploymentCandidate(deployment_id=i, sensor_type=t, removal_date=r)
        for i, t, r in rows
    ]


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
