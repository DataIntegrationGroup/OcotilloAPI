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
Run a Cloud Run job execution and wait for it, over the Cloud Run Admin API v2.

Dagster+ Serverless is a poor place for heavy work -- small runners, outside
GCP, a long way from the database -- so the export's steps run as Cloud Run job
executions in the project, next to Cloud SQL and the bucket, and the Dagster
op only launches and watches them. Each step is one ``jobs:run`` call with the
step's arguments as a container override.

Plain REST through ``google-auth``'s ``AuthorizedSession`` rather than the
``google-cloud-run`` client: three endpoints do not justify another dependency
tree in the code location.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

API = "https://run.googleapis.com/v2"


class CloudRunExecutionFailed(RuntimeError):
    def __init__(self, message: str, execution: "CloudRunExecution | None" = None):
        super().__init__(message)
        self.execution = execution


@dataclass
class CloudRunExecution:
    name: str
    log_uri: str | None = None
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    task_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def short_name(self) -> str:
        return self.name.rsplit("/", 1)[-1]

    @classmethod
    def from_api(cls, body: dict[str, Any]) -> "CloudRunExecution":
        return cls(
            name=body.get("name", ""),
            log_uri=body.get("logUri"),
            succeeded=int(body.get("succeededCount", 0)),
            failed=int(body.get("failedCount", 0)),
            cancelled=int(body.get("cancelledCount", 0)),
            task_count=int(body.get("taskCount", 0)),
            raw=body,
        )


def authorized_session() -> Any:
    """An HTTP session carrying the code location's Google credentials."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    from automated_ingestion.shared.credentials import (
        ensure_application_default_credentials,
    )

    ensure_application_default_credentials()
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def run_job(
    session: Any,
    job_name: str,
    args: list[str],
    task_count: int = 1,
    timeout_seconds: int = 3600,
    env: dict[str, str] | None = None,
    poll_seconds: float = 15.0,
    log: Callable[[str], None] = lambda _: None,
    sleep: Callable[[float], None] = time.sleep,
) -> CloudRunExecution:
    """Execute ``job_name`` with ``args`` and block until it finishes.

    ``job_name`` is the full resource name,
    ``projects/<p>/locations/<r>/jobs/<job>``. Raises
    ``CloudRunExecutionFailed`` unless every task succeeded. If the wait is
    interrupted -- the Dagster run terminated -- the execution is cancelled
    rather than left running unwatched.
    """
    container: dict[str, Any] = {"args": args}
    if env:
        container["env"] = [{"name": k, "value": v} for k, v in env.items()]
    body = {
        "overrides": {
            "containerOverrides": [container],
            "taskCount": task_count,
            "timeout": f"{int(timeout_seconds)}s",
        }
    }

    response = session.post(f"{API}/{job_name}:run", json=body, timeout=60)
    _raise_for(response, f"run {job_name}")
    operation = response.json()
    execution_name = (operation.get("metadata") or {}).get("name", "")
    log(
        f"started {execution_name or operation.get('name')} "
        f"({task_count} task{'s' if task_count != 1 else ''}): {' '.join(args)}"
    )

    # The operation finishes when the execution does. Allow the execution's own
    # timeout plus slack for scheduling, then give up on it.
    deadline = time.monotonic() + timeout_seconds + 600
    try:
        while not operation.get("done"):
            if time.monotonic() > deadline:
                raise CloudRunExecutionFailed(
                    f"{execution_name} did not finish within {timeout_seconds}s"
                )
            sleep(poll_seconds)
            response = session.get(f"{API}/{operation['name']}", timeout=60)
            _raise_for(response, f"poll {operation['name']}")
            operation = response.json()
    except BaseException:
        if execution_name and not operation.get("done"):
            _cancel(session, execution_name, log)
        raise

    if "error" in operation:
        error = operation["error"]
        execution = CloudRunExecution.from_api(operation.get("metadata") or {})
        raise CloudRunExecutionFailed(
            f"{execution_name} failed: {error.get('message', error)}"
            + (f" -- logs: {execution.log_uri}" if execution.log_uri else ""),
            execution,
        )

    execution = CloudRunExecution.from_api(
        operation.get("response") or operation.get("metadata") or {}
    )
    if execution.failed or execution.cancelled or execution.succeeded < task_count:
        raise CloudRunExecutionFailed(
            f"{execution.short_name}: {execution.succeeded}/{task_count} tasks "
            f"succeeded, {execution.failed} failed, {execution.cancelled} "
            f"cancelled -- logs: {execution.log_uri}",
            execution,
        )
    log(f"{execution.short_name} succeeded ({execution.succeeded} tasks)")
    return execution


def _cancel(session: Any, execution_name: str, log: Callable[[str], None]) -> None:
    try:
        session.post(f"{API}/{execution_name}:cancel", json={}, timeout=60)
        log(f"cancelled {execution_name}")
    except Exception as exc:  # noqa: BLE001 - best effort while unwinding
        log(f"could not cancel {execution_name}: {exc}")


def _raise_for(response: Any, what: str) -> None:
    if response.status_code >= 400:
        raise CloudRunExecutionFailed(
            f"{what}: HTTP {response.status_code} {response.text[:500]}"
        )


# ============= EOF =============================================
