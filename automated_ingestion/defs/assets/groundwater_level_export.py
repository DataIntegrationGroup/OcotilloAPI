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
Groundwater level bulk export (OCO-79): five assets, five Cloud Run executions.

    gwl_snapshot -> gwl_well_files -> gwl_checks -> gwl_published_files -> gwl_stac_items

Each asset launches one execution of the ``gwl-export`` Cloud Run job with its
step as the container argument, waits for it, then reads the step's report
back from the export bucket and attaches it as metadata. The work happens in
Cloud Run; Dagster owns order, retries, schedule and the record of what each
run did.

The value passed between assets is the snapshot id, nothing more. Re-running a
downstream asset alone therefore re-runs its step against the last snapshot,
which is what makes "publish failed, fix IAM, re-materialize publish" work
without re-reading the database.
"""

import math
from typing import Any

from dagster import (
    AssetExecutionContext,
    Config,
    MetadataValue,
    Output,
    asset,
)

from automated_ingestion.defs.resources import CloudRunJob, ExportStorage

GROUP = "groundwater_level_export"


def _execute(
    context: AssetExecutionContext,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
    step: str,
    snapshot_id: str,
    task_count: int = 1,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Run ``step`` in Cloud Run; return metadata describing the execution."""
    execution = cloud_run.run(
        context,
        [step, "--snapshot-id", snapshot_id, "--root", export_storage.root],
        task_count=task_count,
        timeout_seconds=timeout_seconds,
    )
    metadata: dict[str, Any] = {
        "snapshot_id": MetadataValue.text(snapshot_id),
        "cloud_run_execution": MetadataValue.text(execution.short_name),
        "cloud_run_tasks": MetadataValue.int(task_count),
    }
    if execution.log_uri:
        metadata["cloud_run_logs"] = MetadataValue.url(execution.log_uri)
    return metadata


def _report(export_storage: ExportStorage, snapshot_id: str, step: str) -> dict:
    from automated_ingestion.exports.groundwater_levels.steps import read_report

    return read_report(export_storage.open(), snapshot_id, step)


@asset(
    group_name=GROUP,
    description=(
        "Step 1. A consistent snapshot of every public groundwater level, read "
        "from the replica in one REPEATABLE READ transaction, with each well's "
        "content hash compared against what was last published."
    ),
)
def gwl_snapshot(
    context: AssetExecutionContext,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
) -> Output[str]:
    from datetime import datetime, timezone

    from automated_ingestion.exports.groundwater_levels.rules import new_snapshot_id

    snapshot_id = new_snapshot_id(datetime.now(tz=timezone.utc), context.run.run_id)
    metadata = _execute(context, cloud_run, export_storage, "snapshot", snapshot_id)
    report = _report(export_storage, snapshot_id, "snapshot")
    return Output(
        snapshot_id,
        metadata={
            **metadata,
            "rows": MetadataValue.int(report["rows"]),
            "wells": MetadataValue.int(report["wells"]),
            "wells_changed": MetadataValue.int(report["changed"]),
            "wells_unchanged": MetadataValue.int(report["unchanged"]),
            "wells_withdrawn": MetadataValue.int(report["withdrawn"]),
        },
    )


class WellFilesConfig(Config):
    wells_per_task: int = 250
    """Changed wells each parallel Cloud Run task converts."""
    max_tasks: int = 50
    """Ceiling on parallel tasks. A first run converts every well."""


@asset(
    group_name=GROUP,
    description=(
        "Step 2. GeoParquet (ZSTD) and CSV for each changed well, full history, "
        "long format, sorted by time. Fans out across parallel Cloud Run tasks; "
        "launches nothing when no well changed."
    ),
)
def gwl_well_files(
    context: AssetExecutionContext,
    config: WellFilesConfig,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
    gwl_snapshot: str,
) -> Output[str]:
    snapshot_id = gwl_snapshot
    changed = _report(export_storage, snapshot_id, "snapshot")["changed"]
    if changed == 0:
        context.log.info("no well changed since the last publish; nothing to convert")
        return Output(
            snapshot_id,
            metadata={
                "snapshot_id": MetadataValue.text(snapshot_id),
                "wells_converted": MetadataValue.int(0),
                "cloud_run_tasks": MetadataValue.int(0),
            },
        )

    tasks = max(1, min(config.max_tasks, math.ceil(changed / config.wells_per_task)))
    metadata = _execute(
        context, cloud_run, export_storage, "convert", snapshot_id, task_count=tasks
    )

    from automated_ingestion.exports.groundwater_levels.rules import run_paths
    from automated_ingestion.exports.groundwater_levels.storage import read_json

    storage = export_storage.open()
    reports = [
        read_json(storage, p)
        for p in storage.list(run_paths(snapshot_id)["reports"])
        if p.rsplit("/", 1)[-1].startswith("convert-")
    ]
    return Output(
        snapshot_id,
        metadata={
            **metadata,
            "wells_converted": MetadataValue.int(sum(r["wells"] for r in reports)),
            "rows_written": MetadataValue.int(sum(r["rows"] for r in reports)),
        },
    )


@asset(
    group_name=GROUP,
    description=(
        "Step 3. Checks every staged file: row counts match the database, "
        "schema matches, no null ids, sorted by time, depths in range. Fails "
        "the run -- and so blocks publication -- on any error."
    ),
)
def gwl_checks(
    context: AssetExecutionContext,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
    gwl_well_files: str,
) -> Output[str]:
    snapshot_id = gwl_well_files
    metadata = _execute(
        context, cloud_run, export_storage, "check", snapshot_id, timeout_seconds=1800
    )
    report = _report(export_storage, snapshot_id, "check")
    if report["warnings"]:
        context.log.warning(
            "%s wells have out-of-range values (published anyway): %s",
            len(report["warnings"]),
            ", ".join(sorted(report["warnings"])[:20]),
        )
    return Output(
        snapshot_id,
        metadata={
            **metadata,
            "wells_checked": MetadataValue.int(report["wells_checked"]),
            "wells_with_warnings": MetadataValue.int(len(report["warnings"])),
            "warnings": MetadataValue.json(report["warnings"]),
        },
    )


@asset(
    group_name=GROUP,
    description=(
        "Step 4. Copies checked files to their fixed paths "
        "(groundwater-levels/<well>/gwl-<well>.parquet|.csv) and deletes the "
        "files of wells that are no longer public."
    ),
)
def gwl_published_files(
    context: AssetExecutionContext,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
    gwl_checks: str,
) -> Output[str]:
    snapshot_id = gwl_checks
    metadata = _execute(
        context, cloud_run, export_storage, "publish", snapshot_id, timeout_seconds=1800
    )
    report = _report(export_storage, snapshot_id, "publish")
    return Output(
        snapshot_id,
        metadata={
            **metadata,
            "wells_published": MetadataValue.int(report["published"]),
            "wells_withdrawn": MetadataValue.int(report["withdrawn"]),
        },
    )


@asset(
    group_name=GROUP,
    description=(
        "Step 5. Inserts or updates STAC item gwl-<well> in the "
        "groundwater-levels collection for each changed well, removes withdrawn "
        "ones, and commits the published state. Until this succeeds the next "
        "run redoes everything."
    ),
)
def gwl_stac_items(
    context: AssetExecutionContext,
    cloud_run: CloudRunJob,
    export_storage: ExportStorage,
    gwl_published_files: str,
) -> Output[str]:
    snapshot_id = gwl_published_files
    metadata = _execute(context, cloud_run, export_storage, "register", snapshot_id)
    report = _report(export_storage, snapshot_id, "register")
    return Output(
        snapshot_id,
        metadata={
            **metadata,
            "items_registered": MetadataValue.int(report["registered"]),
            "items_withdrawn": MetadataValue.int(report["withdrawn"]),
            "stac_api": MetadataValue.text(report["stac_api"]),
        },
    )


GROUNDWATER_LEVEL_EXPORT_ASSETS = [
    gwl_snapshot,
    gwl_well_files,
    gwl_checks,
    gwl_published_files,
    gwl_stac_items,
]


# ============= EOF =============================================
