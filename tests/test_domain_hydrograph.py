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
"""Rules behind publishing and range-deleting corrected transducer series."""

from datetime import date, datetime, timedelta, timezone

import pytest

from domain.hydrograph import (
    HydrographError,
    derive_block_span,
    first_out_of_order_index,
    narrowed_block_span,
    resolve_deployment_id,
    spans_overlap,
    validate_delete_range,
)

T0 = datetime(2025, 1, 15, tzinfo=timezone.utc)


def _times(*hours):
    return [T0 + timedelta(hours=h) for h in hours]


# --------------------------------------------------------------------------
# derive_block_span
# --------------------------------------------------------------------------
def test_span_is_the_extent_of_the_readings():
    assert derive_block_span(_times(0, 6, 12)) == (T0, T0 + timedelta(hours=12))


def test_span_does_not_assume_the_readings_arrived_sorted():
    assert derive_block_span(_times(12, 0, 6)) == (T0, T0 + timedelta(hours=12))


def test_a_single_reading_gives_a_zero_width_span():
    # Allowed on purpose: the block check constraint is `end >= start` and the
    # reader matches inclusively, so one reading still gets covered.
    assert derive_block_span(_times(0)) == (T0, T0)


def test_empty_series_is_rejected():
    with pytest.raises(HydrographError):
        derive_block_span([])


# --------------------------------------------------------------------------
# first_out_of_order_index
# --------------------------------------------------------------------------
def test_increasing_series_is_in_order():
    assert first_out_of_order_index(_times(0, 6, 12)) is None


def test_going_backwards_is_reported_at_the_offending_row():
    assert first_out_of_order_index(_times(0, 12, 6)) == 2


def test_a_repeated_timestamp_is_reported_too():
    # Not merely untidy: two readings at one instant collide on the
    # deployment/parameter/datetime constraint and would abort the insert.
    assert first_out_of_order_index(_times(0, 6, 6)) == 2


def test_a_single_row_cannot_be_out_of_order():
    assert first_out_of_order_index(_times(0)) is None


# --------------------------------------------------------------------------
# spans_overlap
# --------------------------------------------------------------------------
def test_disjoint_spans_do_not_overlap():
    assert not spans_overlap(
        T0, T0 + timedelta(1), T0 + timedelta(2), T0 + timedelta(3)
    )


def test_nested_span_overlaps():
    assert spans_overlap(
        T0 + timedelta(1), T0 + timedelta(2), T0, T0 + timedelta(days=10)
    )


def test_spans_touching_at_one_instant_overlap():
    # The distinguishing case. `TransducerObservationBlock.overlaps` is
    # half-open and would call this clear; the reader is inclusive, so both
    # blocks would claim a reading at the shared instant.
    assert spans_overlap(T0, T0 + timedelta(1), T0 + timedelta(1), T0 + timedelta(2))


# --------------------------------------------------------------------------
# resolve_deployment_id
# --------------------------------------------------------------------------
SPAN_START = datetime(2025, 3, 1, tzinfo=timezone.utc)
SPAN_END = datetime(2025, 3, 31, tzinfo=timezone.utc)


def test_the_one_covering_deployment_is_chosen():
    candidates = [
        (1, date(2020, 1, 1), date(2021, 1, 1)),
        (2, date(2025, 1, 1), None),
    ]
    assert resolve_deployment_id(candidates, SPAN_START, SPAN_END) == 2


def test_a_null_installation_date_reads_as_always_installed():
    assert resolve_deployment_id([(7, None, None)], SPAN_START, SPAN_END) == 7


def test_a_deployment_removed_mid_span_does_not_cover_it():
    with pytest.raises(HydrographError, match="No deployment covers"):
        resolve_deployment_id(
            [(1, date(2025, 1, 1), date(2025, 3, 15))], SPAN_START, SPAN_END
        )


def test_no_deployments_at_all_is_an_error_naming_the_way_out():
    with pytest.raises(HydrographError, match="send deployment_id explicitly"):
        resolve_deployment_id([], SPAN_START, SPAN_END)


def test_two_covering_deployments_are_ambiguous_rather_than_a_coin_flip():
    with pytest.raises(HydrographError, match="2 deployments cover"):
        resolve_deployment_id(
            [(1, date(2024, 1, 1), None), (2, None, None)], SPAN_START, SPAN_END
        )


# --------------------------------------------------------------------------
# narrowed_block_span
# --------------------------------------------------------------------------
def test_a_block_with_nothing_left_is_marked_for_deletion():
    assert narrowed_block_span([]) is None


def test_a_block_narrows_to_what_survived():
    assert narrowed_block_span(_times(6, 12)) == (
        T0 + timedelta(hours=6),
        T0 + timedelta(hours=12),
    )


def test_a_block_down_to_one_reading_becomes_zero_width():
    assert narrowed_block_span(_times(6)) == (
        T0 + timedelta(hours=6),
        T0 + timedelta(hours=6),
    )


# --------------------------------------------------------------------------
# validate_delete_range
# --------------------------------------------------------------------------
def test_a_forward_range_is_accepted():
    assert validate_delete_range(T0, T0 + timedelta(1)) is None


def test_an_inverted_range_is_rejected_not_reordered():
    # The operation is irreversible; a transposed pair is as likely to be the
    # wrong pair as the right one written backwards.
    with pytest.raises(HydrographError, match="after start_time"):
        validate_delete_range(T0 + timedelta(1), T0)


def test_a_zero_width_range_is_rejected():
    with pytest.raises(HydrographError):
        validate_delete_range(T0, T0)
