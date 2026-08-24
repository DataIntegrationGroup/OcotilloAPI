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


# ============= EOF =============================================
