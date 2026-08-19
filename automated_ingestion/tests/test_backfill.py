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
Backfill primitives. Pure, so none of this needs a database or a network.
"""

from datetime import datetime, timezone

import pytest

from automated_ingestion.shared.backfill import (
    Chunk,
    ChunkResult,
    InMemoryCheckpointStore,
    attach_run_timestamp,
    chunk_key,
    month_chunks,
    parse_backfill_date,
    pending_chunks,
    resolve_location_ids,
    sanitize_run_key,
    sum_chunk_results,
    validate_date_order,
)


def _utc(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc)


class TestMonthChunks:
    def test_window_is_split_on_calendar_months(self):
        chunks = list(month_chunks(_utc(2026, 1, 15), _utc(2026, 4, 10)))
        assert [c.key for c in chunks] == ["2026-01", "2026-02", "2026-03", "2026-04"]

    def test_edges_are_clipped_not_widened(self):
        # Widening would fetch data the operator did not ask for.
        chunks = list(month_chunks(_utc(2026, 1, 15), _utc(2026, 2, 10)))
        assert chunks[0].start == _utc(2026, 1, 15)
        assert chunks[-1].end == _utc(2026, 2, 10)

    def test_chunks_do_not_overlap(self):
        chunks = list(month_chunks(_utc(2025, 11, 3), _utc(2026, 3, 20)))
        for earlier, later in zip(chunks, chunks[1:]):
            assert earlier.end < later.start

    def test_window_inside_one_month_is_a_single_chunk(self):
        assert len(list(month_chunks(_utc(2026, 1, 5), _utc(2026, 1, 20)))) == 1

    def test_year_boundary(self):
        chunks = list(month_chunks(_utc(2025, 12, 20), _utc(2026, 1, 10)))
        assert [c.key for c in chunks] == ["2025-12", "2026-01"]

    def test_reversed_window_is_rejected(self):
        with pytest.raises(ValueError, match="must be after"):
            list(month_chunks(_utc(2026, 5, 1), _utc(2026, 1, 1)))


class TestDates:
    def test_bare_date_is_utc_midnight(self):
        assert parse_backfill_date("2026-01-15") == _utc(2026, 1, 15)

    def test_naive_datetime_is_read_as_utc(self):
        # The same run config must mean the same window on every machine.
        assert parse_backfill_date("2026-01-15T00:00:00") == _utc(2026, 1, 15)

    def test_offset_is_normalized(self):
        assert parse_backfill_date("2026-01-14T18:00:00-06:00") == _utc(2026, 1, 15)

    @pytest.mark.parametrize("value", ["", "   ", "yesterday", None])
    def test_unusable_dates_are_rejected(self, value):
        with pytest.raises(ValueError):
            parse_backfill_date(value)

    def test_empty_window_is_rejected(self):
        # A backfill that succeeds having done nothing is indistinguishable from
        # one that worked, and the operator never learns they typed the dates
        # backwards.
        with pytest.raises(ValueError):
            validate_date_order(_utc(2026, 1, 1), _utc(2026, 1, 1))


class TestRunKeys:
    def test_path_separators_are_removed(self):
        # An unsanitized key with a slash writes checkpoints into a directory of
        # its own, and a resumed run does not find them.
        assert "/" not in sanitize_run_key("march/gap")

    def test_unusable_keys_are_rejected(self):
        with pytest.raises(ValueError):
            sanitize_run_key("///")

    def test_timestamp_is_appended_only_when_asked(self):
        stamped = attach_run_timestamp("gap", now=_utc(2026, 1, 15))
        assert stamped == "gap-20260115T000000Z"

    def test_chunk_key_combines_run_and_month(self):
        chunk = Chunk(start=_utc(2026, 3, 1), end=_utc(2026, 3, 31))
        assert chunk_key("march gap", chunk) == "march-gap/2026-03"


class TestLocationIds:
    def test_empty_request_means_everything(self):
        assert resolve_location_ids([], [39, 40, 41]) == [39, 40, 41]

    def test_unknown_ids_fail_the_run(self):
        # Silently backfilling nothing looks identical to backfilling
        # successfully, and the gap is still there weeks later.
        with pytest.raises(ValueError, match="99"):
            resolve_location_ids([39, 99], [39, 40])

    def test_error_names_every_bad_id(self):
        with pytest.raises(ValueError) as exc:
            resolve_location_ids([98, 99], [39])
        assert "98" in str(exc.value) and "99" in str(exc.value)

    def test_requested_subset_is_preserved(self):
        assert resolve_location_ids([41, 39], [39, 40, 41]) == [41, 39]


class TestCheckpoints:
    def test_pending_excludes_completed(self):
        store = InMemoryCheckpointStore()
        chunks = list(month_chunks(_utc(2026, 1, 1), _utc(2026, 4, 1)))
        store.mark_complete("gap", chunks[0])
        assert [c.key for c in pending_chunks(store, "gap", chunks)] == [
            "2026-02",
            "2026-03",
        ]

    def test_checkpoints_are_scoped_to_the_run(self):
        store = InMemoryCheckpointStore()
        chunks = list(month_chunks(_utc(2026, 1, 1), _utc(2026, 3, 1)))
        store.mark_complete("gap", chunks[0])
        assert len(pending_chunks(store, "other", chunks)) == 2

    def test_run_key_is_sanitized_consistently(self):
        # Marking under one spelling and resuming under another must not lose
        # the checkpoint.
        store = InMemoryCheckpointStore()
        chunk = Chunk(start=_utc(2026, 1, 1), end=_utc(2026, 1, 31))
        store.mark_complete("march gap", chunk)
        assert store.completed("march-gap") == {"2026-01"}


class TestTotals:
    def test_totals_sum_across_chunks(self):
        totals = sum_chunk_results(
            [
                ChunkResult("2026-01", rows_ingested=100, rows_upserted=98, failures=2),
                ChunkResult("2026-02", rows_ingested=50, rows_upserted=50),
            ]
        )
        assert totals.chunks == 2
        assert totals.rows_ingested == 150
        assert totals.rows_upserted == 148
        assert totals.failures == 2
        assert totals.chunk_keys == ["2026-01", "2026-02"]

    def test_refused_rows_are_derived(self):
        assert (
            ChunkResult("2026-01", rows_ingested=10, rows_upserted=7).rows_refused == 3
        )


# ============= EOF =============================================
