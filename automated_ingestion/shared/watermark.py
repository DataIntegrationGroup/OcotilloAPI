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
Where a series got to, asked of the data rather than of a sidecar.

Aqueduct keeps watermarks in a GCS object beside the raw zone, because its
destination is FROST and cannot be queried cheaply for a maximum. Ocotillo's
destination is Postgres, so the watermark is simply
``MAX(observation_datetime)`` for the series.

**This is a deliberate divergence, not an oversight.** A stored watermark is a
second source of truth about what was loaded, and the two drift: a load that
half-succeeds, or a sidecar write that fails after the rows commit, leaves the
watermark claiming more or less than the data holds. Deriving it means the
answer cannot disagree with reality — and it makes a backfill safe by
construction, since re-loading an old window cannot move a maximum forward.

**Keyed by thing, not by deployment.** Observations carry ``deployment_id``, but
a series outlives its hardware: replacing a diver creates a new deployment for
the same well, and a watermark keyed to the deployment would report nothing for
the new one and re-fetch the entire history. The query joins through
``deployment`` to ask the question the pipeline actually has -- how far along is
this well's depth-to-water record.
"""

from datetime import datetime
from typing import Any, Protocol


class WatermarkStore(Protocol):
    """Where a series has been loaded up to."""

    def get(self, thing_id: int, parameter_id: int) -> datetime | None:
        """Latest observation for the series, or ``None`` if never loaded."""
        ...


class PostgresWatermarkStore:
    """Reads the watermark from the observations themselves.

    Takes the session the loader is using, so the watermark reflects that
    session's committed state rather than a separate connection's snapshot.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    def get(self, thing_id: int, parameter_id: int) -> datetime | None:
        from sqlalchemy import func, select

        from db.deployment import Deployment
        from db.transducer import TransducerObservation

        return self._session.scalar(
            select(func.max(TransducerObservation.observation_datetime))
            .join(
                Deployment,
                Deployment.id == TransducerObservation.deployment_id,
            )
            .where(Deployment.thing_id == thing_id)
            .where(TransducerObservation.parameter_id == parameter_id)
        )


class InMemoryWatermarkStore:
    """For tests, and for reasoning about a run without a database."""

    def __init__(self, watermarks: dict[tuple[int, int], datetime] | None = None):
        self._watermarks = dict(watermarks or {})

    def get(self, thing_id: int, parameter_id: int) -> datetime | None:
        return self._watermarks.get((thing_id, parameter_id))

    def set(self, thing_id: int, parameter_id: int, value: datetime) -> None:
        self._watermarks[(thing_id, parameter_id)] = value


def resolve_start(
    store: WatermarkStore,
    thing_id: int,
    parameter_id: int,
    floor: datetime,
) -> datetime:
    """Where the next fetch should begin.

    ``floor`` applies only to a series that has never been loaded. It is not a
    backfill lever: lowering it will not re-fetch history for a series whose
    watermark has already advanced past it, because the watermark wins whenever
    one exists. Re-fetching history is what the backfill jobs are for.
    """
    watermark = store.get(thing_id, parameter_id)
    return watermark if watermark is not None else floor


# ============= EOF =============================================
