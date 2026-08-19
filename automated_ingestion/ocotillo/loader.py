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
Idempotent loading of observations into Ocotillo.

Every write is an upsert against the unique constraint on
``(deployment_id, parameter_id, observation_datetime)``. That makes a re-run a
no-op rather than a duplication, which is what lets a backfill overlap existing
data safely.

The alternative -- delete the window, then insert -- is what Aqueduct does
against FROST, because there is no constraint there to conflict on. It leaves a
window during which the data is simply missing, and a failure mid-way leaves it
missing permanently. Upserting has no such window.

Rows are written with SQLAlchemy Core rather than ORM objects. ``AGENTS.md``
is explicit about this for high-volume tables: instantiating a mapped class per
observation is what turns a backfill into an hour-long run.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

DEFAULT_BATCH_SIZE = 5_000
"""Rows per statement.

Large enough that a month of five-minute readings is a handful of round trips,
small enough that one batch's parameters do not approach Postgres' limit. Each
batch commits on its own, so an interrupted load keeps what it had already
written -- with an upsert, resuming simply rewrites those rows.
"""


@dataclass
class LoadResult:
    """What a load did, for reporting as asset metadata."""

    rows_seen: int = 0
    rows_written: int = 0
    batches: int = 0
    blocks_touched: list[int] = field(default_factory=list)

    @property
    def rows_skipped(self) -> int:
        return self.rows_seen - self.rows_written


def _batched(records: Iterable[Any], size: int) -> Iterator[list[Any]]:
    batch: list[Any] = []
    for record in records:
        batch.append(record)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


DEFAULT_DATA_MATURITY = "provisional"
"""Maturity for a freshly ingested reading.

USGS publishes unapproved records as provisional -- "provisional data subject to
revision" -- and that is what a diver reading is until somebody reviews it.
Orthogonal to ``release_status``: San Acacia data is public *and* provisional,
which is why this is a second column rather than another value in the first.
"""


def load_observations(
    session: Any,
    records: Iterable[Any],
    deployment_id: int,
    parameter_id: int,
    release_status: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    data_maturity: str = DEFAULT_DATA_MATURITY,
) -> LoadResult:
    """Upsert observations, committing per batch.

    ``records`` are ``ObservationRecord`` values from an adapter; resolving a
    source's point identifier to a deployment belongs to reference-data
    bootstrapping, not here, so the caller supplies the ids.
    """
    from sqlalchemy.dialects.postgresql import insert

    from db.transducer import TransducerObservation

    result = LoadResult()
    table = TransducerObservation.__table__

    for batch in _batched(records, batch_size):
        rows = [
            {
                "deployment_id": deployment_id,
                "parameter_id": parameter_id,
                "observation_datetime": record.observation_datetime,
                "value": record.value,
                "release_status": release_status,
                "data_maturity": data_maturity,
            }
            for record in batch
        ]
        result.rows_seen += len(rows)

        statement = insert(table).values(rows)
        # DO UPDATE rather than DO NOTHING: a vendor may correct a reading, and
        # a correction arriving as a no-op would leave the old value in place
        # while the run reported success.
        statement = statement.on_conflict_do_update(
            index_elements=[
                "deployment_id",
                "parameter_id",
                "observation_datetime",
            ],
            set_={
                "value": statement.excluded.value,
                "data_maturity": statement.excluded.data_maturity,
            },
        )
        session.execute(statement)
        session.commit()

        result.rows_written += len(rows)
        result.batches += 1

    return result


def ensure_block(
    session: Any,
    thing_id: int,
    parameter_id: int,
    start: datetime,
    end: datetime,
    release_status: str,
    review_status: str = "not reviewed",
) -> int:
    """Create or widen the QC block covering a loaded window.

    ``review_status`` defaults to ``not reviewed`` and callers should leave it
    there. In Ocotillo ``approved`` asserts that a Bureau human reviewed the
    data and carries a ``reviewer_id``; the vendor's own approval flag is a
    different claim and is preserved separately.

    An existing block is widened rather than duplicated, so re-running a window
    does not accumulate blocks.
    """
    from sqlalchemy import select

    from db.transducer import TransducerObservationBlock

    existing = session.scalars(
        select(TransducerObservationBlock)
        .where(TransducerObservationBlock.thing_id == thing_id)
        .where(TransducerObservationBlock.parameter_id == parameter_id)
        .where(TransducerObservationBlock.review_status == review_status)
        .where(TransducerObservationBlock.start_datetime <= end)
        .where(TransducerObservationBlock.end_datetime >= start)
    ).first()

    if existing is not None:
        existing.start_datetime = min(existing.start_datetime, start)
        existing.end_datetime = max(existing.end_datetime, end)
        session.commit()
        return existing.id

    block = TransducerObservationBlock(
        thing_id=thing_id,
        parameter_id=parameter_id,
        review_status=review_status,
        start_datetime=start,
        end_datetime=end,
        release_status=release_status,
    )
    session.add(block)
    session.commit()
    return block.id


# ============= EOF =============================================
