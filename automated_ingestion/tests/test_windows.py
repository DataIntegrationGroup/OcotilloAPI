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
"""Window arithmetic, including the refusal to shrink past the floor."""

import pytest

from automated_ingestion.shared.windows import (
    DAY,
    MINIMUM_SPAN,
    Window,
    iter_windows,
)


def test_windows_cover_the_range_without_gaps_or_overlap():
    windows = list(iter_windows(0, 10 * DAY, span=3 * DAY))
    assert windows[0].start == 0
    assert windows[-1].end == 10 * DAY
    for earlier, later in zip(windows, windows[1:]):
        assert earlier.end == later.start


def test_final_window_is_truncated_not_overshot():
    # Overshooting would ask the API for a future range, which is at best waste
    # and at worst a 400.
    windows = list(iter_windows(0, 10 * DAY, span=3 * DAY))
    assert windows[-1].end == 10 * DAY
    assert windows[-1].span == DAY


def test_range_shorter_than_span_is_a_single_window():
    assert list(iter_windows(0, DAY, span=90 * DAY)) == [Window(0, DAY)]


def test_empty_range_yields_nothing():
    assert list(iter_windows(500, 500)) == []


def test_reversed_range_is_rejected():
    with pytest.raises(ValueError, match="precedes"):
        list(iter_windows(10, 5))


def test_bisect_splits_in_half():
    left, right = Window(0, 100 * DAY).bisect()
    assert left.start == 0
    assert left.end == right.start
    assert right.end == 100 * DAY


def test_bisect_refuses_below_the_floor():
    # A 500 on one day is not a volume problem, and silently halving forever
    # would turn one real failure into an unbounded pile of requests.
    with pytest.raises(ValueError, match="floor"):
        Window(0, MINIMUM_SPAN).bisect()


# ============= EOF =============================================
