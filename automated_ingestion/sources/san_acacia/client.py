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
Client for the private Diver-HUB API.

Three things about this API shape the code, and all three differ from what the
retired FROST pipeline suggested:

1. **Bearer JWT with a real expiry.** ``POST /Accounts/Login`` returns a token
   and a ``validTo`` timestamp. The token is refreshed against that timestamp
   rather than against an assumed lifetime, and once more on a 401 -- a clock
   difference between us and the server should not end a backfill.
2. **Bounded windows.** Readings endpoints take ``startTime``/``endTime`` in
   Unix seconds and answer HTTP 500 when the span is too wide, so a fetch walks
   windows and narrows on failure.
3. **Datum is a request parameter, not a response field.** ``WaterLevels``
   returns ``{dateAndTime, level}``; which datum that level is on depends on the
   ``reference`` value sent. See ``GROUND_SURFACE_REFERENCE``.

Credentials come from the environment and are never logged. The token is not
logged either: it is a bearer credential for the whole account.
"""

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from automated_ingestion.shared.windows import DEFAULT_SPAN, Window, iter_windows

BASE_URL = "https://diver-hub.com/private/api/v1"

USERNAME_ENV_VAR = "DIVERHUB_USERNAME"
PASSWORD_ENV_VAR = "DIVERHUB_PASSWORD"

EXPIRY_SKEW_SECONDS = 60
"""Refresh this long before ``validTo``, so a request in flight at the boundary
does not arrive expired."""

GROUND_SURFACE_REFERENCE: int | None = None
"""Which ``WaterLevelReference`` value means depth below ground surface.

The swagger declares the enum as ``[0, 1, 2, 3]`` with no names, so this cannot
be derived from the specification -- it has to be observed against a well whose
depth to water is independently known. Deliberately ``None`` until then:
guessing wrong would not fail, it would silently record every reading on the
wrong datum, which is the one error this pipeline must not make quietly.

Set it from the finding of `scripts/probe_diverhub.py`.
"""


class Response(Protocol):
    """The subset of a `requests` response this module uses."""

    status_code: int

    def json(self) -> Any: ...


class Transport(Protocol):
    """The subset of a `requests` session this module uses."""

    def post(self, url: str, **kwargs: Any) -> Response: ...

    def get(self, url: str, **kwargs: Any) -> Response: ...


class DiverHubError(RuntimeError):
    """The API refused a request in a way retrying will not fix."""


@dataclass
class _Token:
    value: str
    valid_to: float

    def expired(self, now: float) -> bool:
        return now >= self.valid_to - EXPIRY_SKEW_SECONDS


class DiverHubClient:
    """Authenticated, window-aware access to Diver-HUB."""

    def __init__(
        self,
        transport: Transport,
        username: str | None = None,
        password: str | None = None,
        base_url: str = BASE_URL,
        timeout: int = 60,
    ) -> None:
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._username = username or os.environ.get(USERNAME_ENV_VAR, "")
        self._password = password or os.environ.get(PASSWORD_ENV_VAR, "")
        self._token: _Token | None = None
        if not self._username or not self._password:
            raise DiverHubError(
                f"Diver-HUB credentials are not set. Provide {USERNAME_ENV_VAR} and "
                f"{PASSWORD_ENV_VAR} in the environment."
            )

    # -- authentication ----------------------------------------------------

    def _login(self) -> _Token:
        response = self._transport.post(
            f"{self._base_url}/Accounts/Login",
            json={"username": self._username, "password": self._password},
            timeout=self._timeout,
        )
        if response.status_code == 401:
            raise DiverHubError("Diver-HUB rejected the credentials.")
        if response.status_code != 200:
            raise DiverHubError(f"Login failed with HTTP {response.status_code}.")
        payload = response.json()
        return _Token(
            value=payload["token"],
            valid_to=_parse_timestamp(payload["validTo"]),
        )

    def _authorization(self) -> dict[str, str]:
        if self._token is None or self._token.expired(time.time()):
            self._token = self._login()
        return {"Authorization": f"Bearer {self._token.value}"}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Response:
        """GET with one forced re-login if the token is rejected."""
        response = self._transport.get(
            f"{self._base_url}/{path.lstrip('/')}",
            headers=self._authorization(),
            params=params,
            timeout=self._timeout,
        )
        if response.status_code == 401:
            self._token = None
            response = self._transport.get(
                f"{self._base_url}/{path.lstrip('/')}",
                headers=self._authorization(),
                params=params,
                timeout=self._timeout,
            )
        return response

    # -- reference data ----------------------------------------------------

    def projects(self) -> list[dict[str, Any]]:
        """Projects visible to these credentials."""
        return _expect_ok(self._get("Projects"), "Projects").json()

    def monitoring_points(self, project_id: int) -> list[dict[str, Any]]:
        """Monitoring points in a project. Returns ``{id, name}`` only --
        no coordinates and no construction detail, so geometry and depth have
        to be resolved from Ocotillo rather than from here."""
        path = f"MonitoringPoints/ByProject/{project_id}"
        return _expect_ok(self._get(path), path).json()

    # -- series ------------------------------------------------------------

    def water_levels(
        self,
        monitoring_point_id: int,
        start: int,
        end: int,
        reference: int,
        approved: bool | None = None,
        span: int = DEFAULT_SPAN,
    ) -> Iterator[dict[str, Any]]:
        """Yield ``{dateAndTime, level}`` records across bounded windows.

        ``reference`` selects the datum and is required: there is no safe
        default, because the wrong value produces plausible numbers rather than
        an error.
        """
        params: dict[str, Any] = {"reference": reference}
        if approved is not None:
            params["approved"] = approved
        path = f"WaterLevels/ByMonitoringPoint/{monitoring_point_id}"
        for window in iter_windows(start, end, span):
            yield from self._fetch_window(path, window, params)

    def diver_data(
        self,
        monitoring_point_id: int,
        start: int,
        end: int,
        span: int = DEFAULT_SPAN,
    ) -> Iterator[dict[str, Any]]:
        """Yield raw ``DataPoint`` records -- pressure, temperature, and the
        rest. Not water level; see ``water_levels`` for that."""
        path = f"DiverData/ByMonitoringPoint/{monitoring_point_id}"
        for window in iter_windows(start, end, span):
            yield from self._fetch_window(path, window, {})

    def _fetch_window(
        self, path: str, window: Window, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Fetch one window, halving it on a 500 until it succeeds or hits the
        floor. A 500 here means "too much data", which is the API's way of
        asking to be given a narrower range."""
        response = self._get(
            path, {**params, "startTime": window.start, "endTime": window.end}
        )
        if response.status_code == 500:
            try:
                left, right = window.bisect()
            except ValueError as exc:
                raise DiverHubError(
                    f"{path} returned HTTP 500 for {window.span}s starting "
                    f"{window.start}, which is already at the minimum window. "
                    "This is not a volume problem."
                ) from exc
            yield from self._fetch_window(path, left, params)
            yield from self._fetch_window(path, right, params)
            return
        yield from _expect_ok(response, path).json()


def _expect_ok(response: Response, what: str) -> Response:
    if response.status_code != 200:
        raise DiverHubError(f"{what} returned HTTP {response.status_code}.")
    return response


def _parse_timestamp(value: str) -> float:
    """Parse an ISO-8601 instant into a Unix timestamp.

    The API reports UTC but does not always mark it, so a naive value is read
    as UTC rather than as local time -- reading it as local would shift token
    expiry by the machine's offset and, worse, shift every reading.
    """
    from datetime import datetime, timezone

    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


# ============= EOF =============================================
