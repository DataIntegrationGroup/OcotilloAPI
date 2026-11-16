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
A client for the STAC API Transactions extension -- just insert-or-update and
delete, which is all the export needs.

The STAC API itself is OCO-78 and does not exist yet; this targets the
standard extension (``POST``/``PUT``/``DELETE`` under
``/collections/{id}/items``) that stac-fastapi and pgstac both implement, so it
should need no change when it lands.

Auth, in order of preference:

* ``STAC_API_AUDIENCE`` -- fetch a Google ID token for that audience from the
  Cloud Run job's own service account. Right when the STAC API is itself on
  Cloud Run behind IAM: no secret to store.
* ``STAC_API_TOKEN`` -- a static bearer token, from Secret Manager.
"""

import os
import time
from typing import Any

URL_ENV_VAR = "STAC_API_URL"
AUDIENCE_ENV_VAR = "STAC_API_AUDIENCE"
TOKEN_ENV_VAR = "STAC_API_TOKEN"

_RETRY_STATUSES = {429, 500, 502, 503, 504}


class StacApiError(RuntimeError):
    pass


class StacApiClient:
    def __init__(
        self, base_url: str, session: Any, attempts: int = 4, backoff: float = 2.0
    ):
        self.base_url = base_url.rstrip("/")
        self._session = session
        self._attempts = attempts
        self._backoff = backoff

    def _request(self, method: str, path: str, **kwargs: Any):
        url = f"{self.base_url}{path}"
        for attempt in range(1, self._attempts + 1):
            response = self._session.request(method, url, timeout=60, **kwargs)
            if response.status_code not in _RETRY_STATUSES or attempt == self._attempts:
                return response
            time.sleep(self._backoff**attempt)
        raise AssertionError("unreachable")

    def ensure_collection(self, collection: dict[str, Any]) -> None:
        response = self._request("GET", f"/collections/{collection['id']}")
        if response.status_code == 200:
            return
        if response.status_code != 404:
            raise StacApiError(
                f"GET collection {collection['id']}: {response.status_code} "
                f"{response.text[:500]}"
            )
        response = self._request("POST", "/collections", json=collection)
        if response.status_code not in (200, 201, 409):
            raise StacApiError(
                f"create collection {collection['id']}: {response.status_code} "
                f"{response.text[:500]}"
            )

    def upsert_item(self, collection_id: str, item: dict[str, Any]) -> str:
        """Create the item, or replace it when it exists. Returns which."""
        response = self._request(
            "POST", f"/collections/{collection_id}/items", json=item
        )
        if response.status_code in (200, 201):
            return "created"
        if response.status_code != 409:
            raise StacApiError(
                f"create {item['id']}: {response.status_code} {response.text[:500]}"
            )
        response = self._request(
            "PUT", f"/collections/{collection_id}/items/{item['id']}", json=item
        )
        if response.status_code not in (200, 201, 204):
            raise StacApiError(
                f"update {item['id']}: {response.status_code} {response.text[:500]}"
            )
        return "updated"

    def delete_item(self, collection_id: str, item_id: str) -> None:
        response = self._request(
            "DELETE", f"/collections/{collection_id}/items/{item_id}"
        )
        if response.status_code not in (200, 202, 204, 404):
            raise StacApiError(
                f"delete {item_id}: {response.status_code} {response.text[:500]}"
            )


def client_from_env() -> StacApiClient | None:
    """A client configured from the environment, or None when no URL is set."""
    base_url = os.environ.get(URL_ENV_VAR, "").strip()
    if not base_url:
        return None

    import requests

    session = requests.Session()
    audience = os.environ.get(AUDIENCE_ENV_VAR, "").strip()
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if audience:
        import google.auth.transport.requests
        import google.oauth2.id_token

        token = google.oauth2.id_token.fetch_id_token(
            google.auth.transport.requests.Request(), audience
        )
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    session.headers["Content-Type"] = "application/json"
    return StacApiClient(base_url, session)


# ============= EOF =============================================
