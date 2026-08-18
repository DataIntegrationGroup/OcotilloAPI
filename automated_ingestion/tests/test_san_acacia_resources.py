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
Resource behaviour: failure isolation, approval tagging, and the raw-zone
contract that nothing is converted on the way in.
"""

from automated_ingestion.sources.san_acacia.client import (
    GROUND_SURFACE_REFERENCE,
    DiverHubClient,
)
from automated_ingestion.sources.san_acacia.dlt_pipeline import (
    PROJECT_ID,
    vanessen_locations,
    vanessen_readings,
)
from automated_ingestion.tests.test_diverhub_client import FakeResponse, FakeTransport


class ScriptedTransport(FakeTransport):
    """Answers per-path so a single point can be made to fail."""

    def __init__(self, handler):
        super().__init__()
        self._handler = handler

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self._handler(url, kwargs)


def _points_payload():
    return [{"id": 39, "name": "SO-0125"}, {"id": 40, "name": "SO-0131"}]


def test_locations_flatten_to_the_raw_shape():
    transport = ScriptedTransport(lambda url, kw: FakeResponse(200, _points_payload()))
    client = DiverHubClient(transport, username="u", password="p")
    rows = list(vanessen_locations(client))
    assert rows == [
        {"monitoring_point_id": 39, "name": "SO-0125", "project_id": PROJECT_ID},
        {"monitoring_point_id": 40, "name": "SO-0131", "project_id": PROJECT_ID},
    ]


READINGS = [
    {"dateAndTime": "2026-04-15T22:45:00", "level": 199.356},
    {"dateAndTime": "2026-04-15T23:00:00", "level": 200.0},
]


def _within(rows, params):
    """Return only rows inside the requested window, as the API does.

    A stub that ignores startTime/endTime returns its whole payload for every
    window, which turns a decade-long fetch into fifty copies of the same rows
    and hides whether the caller is windowing correctly at all.
    """
    from automated_ingestion.sources.san_acacia.client import _parse_timestamp

    start, end = params["startTime"], params["endTime"]
    return [r for r in rows if start <= _parse_timestamp(r["dateAndTime"]) <= end]


def _reading_handler(failing_point=None, approved_stamps=()):
    def handler(url, kwargs):
        if "WaterLevels" in url:
            point_id = int(url.rstrip("/").split("/")[-1])
            if point_id == failing_point:
                return FakeResponse(500)
            params = kwargs.get("params", {})
            if params.get("approved"):
                approved = [{"dateAndTime": s, "level": 1.0} for s in approved_stamps]
                return FakeResponse(200, _within(approved, params))
            return FakeResponse(200, _within(READINGS, params))
        return FakeResponse(200, [])

    return handler


def _run_readings(handler, points=None, failures=None):
    transport = ScriptedTransport(handler)
    client = DiverHubClient(transport, username="u", password="p")
    points = (
        points
        if points is not None
        else [
            {"monitoring_point_id": 39, "name": "SO-0125"},
            {"monitoring_point_id": 40, "name": "SO-0131"},
        ]
    )
    collected = failures if failures is not None else []
    resource = vanessen_readings(client, points, 1_800_000_000, collected)
    return list(resource), collected


def test_readings_carry_unit_and_reference_untransformed():
    # The raw zone stores what the vendor said, on the vendor's datum in the
    # vendor's units. Converting here would make a mapping bug a re-fetch
    # instead of a reprocess.
    rows, _ = _run_readings(_reading_handler())
    assert rows[0]["level"] == 199.356
    assert rows[0]["unit"] == "cm"
    assert rows[0]["reference"] == GROUND_SURFACE_REFERENCE


def test_one_failing_point_does_not_lose_the_others():
    rows, failures = _run_readings(_reading_handler(failing_point=39))
    assert [r["monitoring_point_id"] for r in rows] == [40, 40]
    assert len(failures) == 1
    assert failures[0]["monitoring_point_id"] == 39


def test_failures_are_recorded_for_the_caller_not_the_resource():
    # Per-run state on a module-level resource would have concurrent runs
    # overwriting one another.
    own = []
    _run_readings(_reading_handler(failing_point=39), failures=own)
    assert len(own) == 1
    assert not hasattr(vanessen_readings, "failures")


def test_vendor_approval_tags_rows_without_duplicating_them():
    rows, _ = _run_readings(
        _reading_handler(approved_stamps=["2026-04-15T22:45:00"]),
        points=[{"monitoring_point_id": 39, "name": "SO-0125"}],
    )
    # Two readings in, two readings out -- the approved fetch tags, never adds.
    assert len(rows) == 2
    assert rows[0]["vendor_approved"] is True
    assert rows[1]["vendor_approved"] is False


def test_unavailable_approval_flag_does_not_lose_readings():
    def handler(url, kwargs):
        if "WaterLevels" in url:
            params = kwargs.get("params", {})
            if params.get("approved"):
                return FakeResponse(500)
            return FakeResponse(200, _within(READINGS[:1], params))
        return FakeResponse(200, [])

    rows, failures = _run_readings(
        handler, points=[{"monitoring_point_id": 39, "name": "SO-0125"}]
    )
    assert len(rows) == 1
    assert rows[0]["vendor_approved"] is False
    assert failures == []


# ============= EOF =============================================
