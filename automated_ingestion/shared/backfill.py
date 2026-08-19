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
Primitives shared by every backfill, in either mode.

Ported from Aqueduct's ``shared/backfill.py`` rather than imported: the two
repositories deploy separately and are allowed to diverge. Where behaviour
differs from the original it is called out on the function, so the two can be
diffed later by someone who has both open.

**Changed from Aqueduct.** ``ChunkResult`` counts ``rows_upserted`` where the
original counted ``observations_posted`` and ``observations_deleted``. That is
not a rename: Aqueduct deletes a window and re-posts it because FROST has no
constraint to conflict on, so it has two numbers and a window during which the
data is missing. Ocotillo upserts, so there is one number and no window.

Everything here is pure except the checkpoint store, which is why the store is
an interface with an in-memory implementation -- a backfill's chunking and
resumption logic can then be tested without touching object storage.
"""

import re
from calendar import monthrange
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class Chunk:
    """One calendar month of a backfill window, half-open at the end."""

    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        """Stable identifier, used for checkpointing."""
        return self.start.strftime("%Y-%m")


@dataclass
class ChunkResult:
    """What one chunk did.

    ``rows_upserted`` replaces Aqueduct's posted/deleted pair -- see the module
    docstring. ``failures`` counts records the adapter refused, which are
    per-record and never fatal to the chunk.
    """

    chunk_key: str
    rows_ingested: int = 0
    rows_upserted: int = 0
    failures: int = 0

    @property
    def rows_refused(self) -> int:
        return self.rows_ingested - self.rows_upserted


@dataclass
class BackfillTotals:
    """Sum across chunks, for run-level metadata."""

    chunks: int = 0
    rows_ingested: int = 0
    rows_upserted: int = 0
    failures: int = 0
    chunk_keys: list[str] = field(default_factory=list)


def month_chunks(start: datetime, end: datetime) -> Iterator[Chunk]:
    """Split a window into calendar months.

    Calendar months rather than fixed-length windows because that is how a human
    describes a gap ("we lost March"), and because it makes a chunk key legible
    in a checkpoint file. The first and last chunks are clipped to the requested
    range rather than widened to whole months -- widening would fetch data the
    operator did not ask for.
    """
    validate_date_order(start, end)

    cursor = start
    while cursor < end:
        _, last_day = monthrange(cursor.year, cursor.month)
        month_end = cursor.replace(
            day=last_day, hour=23, minute=59, second=59, microsecond=999999
        )
        chunk_end = min(month_end, end)
        yield Chunk(start=cursor, end=chunk_end)

        if chunk_end >= end:
            return
        year = cursor.year + (1 if cursor.month == 12 else 0)
        month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = cursor.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )


def sum_chunk_results(results: Iterable[ChunkResult]) -> BackfillTotals:
    """Aggregate chunk results for reporting."""
    totals = BackfillTotals()
    for result in results:
        totals.chunks += 1
        totals.rows_ingested += result.rows_ingested
        totals.rows_upserted += result.rows_upserted
        totals.failures += result.failures
        totals.chunk_keys.append(result.chunk_key)
    return totals


def parse_backfill_date(value: str) -> datetime:
    """Parse an operator-supplied date into a timezone-aware UTC datetime.

    A bare date means midnight UTC. Accepting a naive value and treating it as
    local time would make the same run config mean different windows on
    different machines.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Backfill date is missing or blank: {value!r}")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Backfill date {value!r} is not ISO-8601.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_date_order(start: datetime, end: datetime) -> None:
    """Reject a reversed or empty window.

    An empty window is rejected rather than treated as a no-op: a backfill that
    reports success having done nothing is indistinguishable from one that
    worked, and the operator would not learn they typed the dates backwards.
    """
    if end <= start:
        raise ValueError(
            f"Backfill end {end.isoformat()} must be after start {start.isoformat()}."
        )


_UNSAFE_RUN_KEY = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_run_key(value: str) -> str:
    """Reduce an operator-supplied run key to something safe as a path segment.

    Run keys end up in object storage paths. An unsanitized one containing a
    slash would silently write checkpoints into a directory of its own, and a
    resumed run would not find them.
    """
    cleaned = _UNSAFE_RUN_KEY.sub("-", (value or "").strip()).strip("-")
    if not cleaned:
        raise ValueError(f"Run key {value!r} contains nothing usable.")
    return cleaned


def attach_run_timestamp(run_key: str, now: datetime | None = None) -> str:
    """Append a UTC timestamp, so two runs with the same key stay distinct.

    Only for keys that are *not* meant to resume. Resumption depends on the key
    being stable, so the caller decides; this never applies it silently.
    """
    stamp = (now or datetime.now(tz=timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{sanitize_run_key(run_key)}-{stamp}"


def chunk_key(run_key: str, chunk: Chunk) -> str:
    """Checkpoint identifier for one chunk of one run."""
    return f"{sanitize_run_key(run_key)}/{chunk.key}"


def resolve_location_ids(
    requested: Iterable[Any], available: Iterable[Any]
) -> list[Any]:
    """Validate requested locations against what the source offers.

    An empty request means every available location. An unknown id fails the
    run, naming the bad ids -- Aqueduct's behaviour, and worth keeping: silently
    backfilling nothing looks identical to backfilling successfully, and the
    operator finds out weeks later that the gap is still there.
    """
    available_list = list(available)
    requested_list = [r for r in requested] if requested is not None else []
    if not requested_list:
        return available_list

    known = set(available_list)
    unknown = [r for r in requested_list if r not in known]
    if unknown:
        raise ValueError(
            "Unknown location ids: "
            + ", ".join(str(u) for u in sorted(unknown, key=str))
            + ". Nothing was backfilled."
        )
    return [r for r in requested_list]


class CheckpointStore(Protocol):
    """Which chunks of a run have completed."""

    def completed(self, run_key: str) -> set[str]: ...

    def mark_complete(self, run_key: str, chunk: Chunk) -> None: ...


class InMemoryCheckpointStore:
    """For tests, and for a dry run that must not persist anything."""

    def __init__(self) -> None:
        self._done: dict[str, set[str]] = {}

    def completed(self, run_key: str) -> set[str]:
        return set(self._done.get(sanitize_run_key(run_key), set()))

    def mark_complete(self, run_key: str, chunk: Chunk) -> None:
        self._done.setdefault(sanitize_run_key(run_key), set()).add(chunk.key)


def pending_chunks(
    store: CheckpointStore, run_key: str, chunks: Iterable[Chunk]
) -> list[Chunk]:
    """Chunks of this run that have not completed yet.

    A chunk is checkpointed only after ingest, transform, and load have all
    succeeded, so anything not marked is safe to redo -- the load is an upsert,
    and redoing a partially loaded chunk rewrites the same rows.
    """
    done = store.completed(run_key)
    return [chunk for chunk in chunks if chunk.key not in done]


# ============= EOF =============================================
