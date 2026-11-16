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
Container entry point for the Cloud Run job: one invocation runs one step.

    python -m automated_ingestion.exports.groundwater_levels.worker \\
        <snapshot|convert|check|publish|register> --snapshot-id ID --root gs://...

Dagster launches the job with these arguments as a container override, so the
same image and job definition serve all five steps. ``convert`` fans out: Cloud
Run sets ``CLOUD_RUN_TASK_INDEX``/``CLOUD_RUN_TASK_COUNT`` on each parallel
task, and each converts its own shard of the changed wells.

Exit status is the contract with Dagster: zero means the step's report is
written and true, anything else fails the execution and the asset.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from automated_ingestion.exports.groundwater_levels import steps
from automated_ingestion.exports.groundwater_levels.storage import open_storage

STEPS = ("snapshot", "convert", "check", "publish", "register")
PUBLIC_BASE_URL_ENV_VAR = "GWL_EXPORT_PUBLIC_BASE_URL"

log = logging.getLogger("gwl_export")


def _public_base_url(root: str) -> str:
    """Where published paths resolve for a downloader.

    Defaults to the bucket's public HTTPS endpoint; override for a CDN or a
    custom domain. Local roots have no public URL, so they need the override.
    """
    configured = os.environ.get(PUBLIC_BASE_URL_ENV_VAR, "").strip()
    if configured:
        return configured
    if root.startswith("gs://"):
        return "https://storage.googleapis.com/" + root[len("gs://") :].rstrip("/")
    raise RuntimeError(f"{PUBLIC_BASE_URL_ENV_VAR} is required for a local root")


def run(step: str, snapshot_id: str, root: str | None = None) -> dict:
    storage = open_storage(root)

    if step == "snapshot":
        from automated_ingestion.exports.groundwater_levels.snapshot import (
            read_snapshot,
        )
        from automated_ingestion.shared.credentials import (
            ensure_application_default_credentials,
        )

        ensure_application_default_credentials()
        from db.engine import session_ctx  # builds the engine from the env

        taken_at = datetime.now(tz=timezone.utc)
        with session_ctx() as session:
            rows, counts = read_snapshot(session)
        return steps.snapshot(storage, snapshot_id, rows, counts, taken_at)

    if step == "convert":
        return steps.convert(
            storage,
            snapshot_id,
            task_index=int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0")),
            task_count=int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1")),
        )

    if step == "check":
        return steps.check(storage, snapshot_id)

    if step == "publish":
        return steps.publish(storage, snapshot_id)

    if step == "register":
        from automated_ingestion.exports.groundwater_levels.stac_api import (
            client_from_env,
        )

        return steps.register(
            storage,
            snapshot_id,
            public_base_url=_public_base_url(storage.root),
            stac=client_from_env(),
        )

    raise ValueError(f"unknown step {step!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gwl-export")
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--root", default=None, help="gs://bucket[/prefix] or a dir")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report = run(args.step, args.snapshot_id, args.root)
    except steps.StepError as exc:
        log.error("%s failed: %s", args.step, exc)
        return 1
    # One JSON line: Cloud Logging parses it into jsonPayload, so a step's
    # outcome is queryable without reading the report from the bucket.
    print(json.dumps({"severity": "INFO", "gwl_export": report}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ============= EOF =============================================
