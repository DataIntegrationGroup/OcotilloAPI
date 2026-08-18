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
Time-window arithmetic for sources that cannot be asked for an open range.

Diver-HUB answers `DiverData` and `WaterLevels` for an explicit
``startTime``/``endTime`` in Unix seconds, and returns HTTP 500 -- not a
pagination cursor, not a 413 -- when the span is too wide. So a "fetch this
series" operation is always a sequence of bounded windows, and the useful
response to a 500 is to ask for less rather than to give up.

Pure arithmetic, no HTTP: the retry policy that uses it is in the client, and
the point of separating them is that the tricky part is testable without a
network.
"""

from collections.abc import Iterator
from dataclasses import dataclass

DAY = 86_400

DEFAULT_SPAN = 90 * DAY
"""Starting window width. Three months is confirmed to work; the ceiling is
not yet measured, so this is the largest span known to be safe rather than the
largest span that is."""

MINIMUM_SPAN = DAY
"""Floor for bisection. A 500 on a single day is a real failure -- something
other than volume -- and must surface rather than shrink forever."""


@dataclass(frozen=True)
class Window:
    """A half-open interval in Unix seconds, ``start`` inclusive."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"Window end {self.end} precedes start {self.start}.")

    @property
    def span(self) -> int:
        return self.end - self.start

    def bisect(self) -> tuple["Window", "Window"]:
        """Split in two. Raises at the floor rather than shrinking forever."""
        if self.span <= MINIMUM_SPAN:
            raise ValueError(
                f"Refusing to split a {self.span}s window below the {MINIMUM_SPAN}s "
                "floor. A failure this narrow is not a volume problem."
            )
        midpoint = self.start + self.span // 2
        return Window(self.start, midpoint), Window(midpoint, self.end)


def iter_windows(start: int, end: int, span: int = DEFAULT_SPAN) -> Iterator[Window]:
    """Walk ``[start, end]`` in windows of at most ``span`` seconds."""
    if span <= 0:
        raise ValueError(f"Window span must be positive, got {span}.")
    if end < start:
        raise ValueError(f"End {end} precedes start {start}.")
    cursor = start
    while cursor < end:
        yield Window(cursor, min(cursor + span, end))
        cursor += span


# ============= EOF =============================================
