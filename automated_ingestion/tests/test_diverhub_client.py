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
Client behaviour that is easy to get wrong and expensive to get wrong:
token refresh, the 401 retry, and narrowing on a 500.

No network. The transport is a stub that records what it was asked for.
"""

import pytest

from automated_ingestion.shared.windows import DAY
from automated_ingestion.sources.san_acacia.client import (
    DiverHubClient,
    DiverHubError,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []

    def json(self):
        return self._payload


class FakeTransport:
    """Records calls and replays queued responses."""

    def __init__(self, get_responses=None, token_valid_for=3600):
        self.posts = []
        self.gets = []
        self._get_responses = list(get_responses or [])
        self._token_valid_for = token_valid_for
        self.login_count = 0

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        self.login_count += 1
        from datetime import datetime, timedelta, timezone

        valid_to = datetime.now(tz=timezone.utc) + timedelta(
            seconds=self._token_valid_for
        )
        return FakeResponse(
            200,
            {"token": f"token-{self.login_count}", "validTo": valid_to.isoformat()},
        )

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if self._get_responses:
            return self._get_responses.pop(0)
        return FakeResponse(200, [])


def _client(transport):
    return DiverHubClient(transport, username="u", password="p")


def test_missing_credentials_fail_fast(monkeypatch):
    monkeypatch.delenv("DIVERHUB_USERNAME", raising=False)
    monkeypatch.delenv("DIVERHUB_PASSWORD", raising=False)
    with pytest.raises(DiverHubError, match="credentials"):
        DiverHubClient(FakeTransport())


def test_token_is_reused_across_calls():
    transport = FakeTransport()
    client = _client(transport)
    client.projects()
    client.projects()
    assert transport.login_count == 1


def test_token_is_refreshed_once_expired():
    # validTo in the past means every call re-authenticates.
    transport = FakeTransport(token_valid_for=-10)
    client = _client(transport)
    client.projects()
    client.projects()
    assert transport.login_count == 2


def test_expiry_skew_refreshes_before_the_deadline():
    # A token valid for 30s is already inside the skew window, so it must not
    # be used: a request in flight at the boundary would arrive expired.
    transport = FakeTransport(token_valid_for=30)
    client = _client(transport)
    client.projects()
    client.projects()
    assert transport.login_count == 2


def test_401_forces_one_reauthentication_and_retry():
    transport = FakeTransport(
        get_responses=[FakeResponse(401), FakeResponse(200, [{"id": 1}])]
    )
    client = _client(transport)
    assert client.projects() == [{"id": 1}]
    assert transport.login_count == 2
    assert len(transport.gets) == 2


def test_500_narrows_the_window_and_stitches_the_halves():
    # First window 500s; each half then succeeds and both are returned.
    transport = FakeTransport(
        get_responses=[
            FakeResponse(500),
            FakeResponse(200, [{"level": 1.0}]),
            FakeResponse(200, [{"level": 2.0}]),
        ]
    )
    client = _client(transport)
    rows = list(client.water_levels(40, 0, 100 * DAY, reference=0, span=100 * DAY))
    assert [r["level"] for r in rows] == [1.0, 2.0]


def test_persistent_500_at_the_floor_is_an_error_not_a_loop():
    transport = FakeTransport(get_responses=[FakeResponse(500)] * 50)
    client = _client(transport)
    with pytest.raises(DiverHubError, match="not a volume problem"):
        list(client.water_levels(40, 0, DAY, reference=0, span=DAY))


def test_water_levels_sends_reference_and_unix_seconds():
    transport = FakeTransport()
    client = _client(transport)
    list(client.water_levels(40, 0, DAY, reference=2, span=DAY))
    _, kwargs = transport.gets[0]
    params = kwargs["params"]
    assert params["reference"] == 2
    assert params["startTime"] == 0
    assert params["endTime"] == DAY
    assert isinstance(params["startTime"], int)


def test_approved_is_omitted_unless_asked_for():
    transport = FakeTransport()
    client = _client(transport)
    list(client.water_levels(40, 0, DAY, reference=0, span=DAY))
    assert "approved" not in transport.gets[0][1]["params"]


def test_naive_valid_to_is_read_as_utc():
    # The API documents UTC but does not always mark it. Reading a naive
    # timestamp as local time would shift expiry by the machine's offset.
    from automated_ingestion.sources.san_acacia.client import _parse_timestamp

    naive = _parse_timestamp("2026-08-18T20:00:00")
    aware = _parse_timestamp("2026-08-18T20:00:00Z")
    assert naive == aware


def test_ground_surface_reference_is_unset_until_confirmed():
    # Guessing would not fail loudly; it would record every reading on the
    # wrong datum. The constant stays None until someone observes it.
    from automated_ingestion.sources.san_acacia import client as module

    assert module.GROUND_SURFACE_REFERENCE is None


# ============= EOF =============================================
