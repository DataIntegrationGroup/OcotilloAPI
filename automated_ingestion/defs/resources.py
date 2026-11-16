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
Dagster resources: the pipeline's handles on the outside world.

The database resource deliberately delegates to ``db/engine.py`` rather than
building its own engine. Connection setup for Cloud SQL -- the connector, IAM
auth, the IP-type choice -- is intricate and already solved there; a second
implementation would be a second thing to get wrong, and would drift.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from dagster import ConfigurableResource


class OcotilloDatabase(ConfigurableResource):
    """A session against the Ocotillo database.

    Configured entirely through the environment that ``db/engine.py`` reads
    (``DB_DRIVER``, ``CLOUD_SQL_*``), so the Dagster+ code location is
    configured the same way the API is, with different credentials.
    """

    @contextmanager
    def session(self) -> Iterator[object]:
        """Yield a SQLAlchemy session, rolled back and closed on the way out."""
        # Credentials first: db.engine builds its Cloud SQL connector at import
        # time, and the connector resolves Application Default Credentials right
        # then. Serverless has none until they are written to disk, so doing this
        # afterwards would be too late.
        from automated_ingestion.shared.credentials import (
            ensure_application_default_credentials,
        )

        ensure_application_default_credentials()

        # Imported lazily: importing db.engine builds an engine from the
        # environment at import time, which should happen when a run asks for a
        # session, not when Dagster loads the code location to list assets.
        from db.engine import session_ctx

        with session_ctx() as session:
            yield session


class CloudRunJob(ConfigurableResource):
    """One Cloud Run job, executed with per-step argument overrides.

    ``project``/``region``/``job`` are set from the environment in
    ``definitions.py`` (``GWL_EXPORT_CLOUD_RUN_*``), so the code location loads
    without them and only a run that needs the job fails when they are missing.
    """

    project: str
    region: str
    job: str
    poll_seconds: float = 15.0

    @property
    def job_name(self) -> str:
        return f"projects/{self.project}/locations/{self.region}/jobs/{self.job}"

    def run(
        self,
        context: Any,
        args: list[str],
        task_count: int = 1,
        timeout_seconds: int = 3600,
    ) -> Any:
        """Execute the job and block until it finishes; raise unless it succeeded."""
        from automated_ingestion.shared.cloud_run import authorized_session, run_job

        return run_job(
            authorized_session(),
            self.job_name,
            args,
            task_count=task_count,
            timeout_seconds=timeout_seconds,
            poll_seconds=self.poll_seconds,
            log=context.log.info,
        )


class ExportStorage(ConfigurableResource):
    """The export root, read by the assets for the reports each step writes."""

    root: str

    def open(self) -> Any:
        from automated_ingestion.exports.groundwater_levels.storage import (
            open_storage,
        )
        from automated_ingestion.shared.credentials import (
            ensure_application_default_credentials,
        )

        ensure_application_default_credentials()
        return open_storage(self.root)


# ============= EOF =============================================
