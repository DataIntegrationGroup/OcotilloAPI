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
Smoke test a deployed Ocotillo API.

What a release runbook asks of a deploy: that the process is up and can reach
PostGIS, that the public OGC mount serves its collections, that the internal
mount is reachable by every credential it is supposed to accept and by nothing
else, and that a user-issued API key can be minted, used, revoked, and is dead
on the next request.

**Read-only.** Nothing here writes: it authenticates with the API key already
in ``.env`` rather than issuing one, because minting a key leaves a row behind
and revoking it leaves another, on whichever database the run points at.

    uv run python -m scripts.smoke_test --base-url https://<host>

    # /api_key and the Authentik-bearer path additionally need a JWT
    uv run python -m scripts.smoke_test --base-url https://<host> \\
        --token "$AUTHENTIK_ACCESS_TOKEN"

``API_KEY`` is read from ``.env`` unless ``--api-key`` or ``SMOKE_API_KEY``
says otherwise, so the internal-mount checks run without being handed a
credential. Point ``--env-file`` elsewhere to smoke a different environment
with its own key, and keep in mind the key has to belong to the host being
tested -- a staging key will simply 401 against production.

Exit status is 0 when nothing failed, 1 when anything did. Checks whose
credentials were not supplied are SKIPped, which is not a failure unless
``--strict`` is passed -- so an unattended run that quietly tested nothing but
``/health`` cannot report success.

The internal mount takes a bearer credential of either kind; the static keys
and user-issued keys are interchangeable there. The API key is additionally
exercised through the two transports the desktop GIS clients need (HTTP Basic,
and ``?token=``), because those paths are what ArcGIS Pro and QGIS actually
use and they are easy to break without noticing. See
docs/internal-ogc-desktop-gis.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Iterable

import httpx
from dotenv import load_dotenv

# Collections the public mount is expected to serve. A short, stable subset
# rather than the whole list: this is a smoke test, and a config that gains a
# collection should not fail it.
EXPECTED_PUBLIC_COLLECTIONS = (
    "latest_tds_wells",
    "actively_monitored_wells",
    "project_areas",
)

# Internal-only, and the reason the mount is gated: it publishes landowner
# contact details and staff access notes. It must never appear on the public
# mount -- there is deliberately no public twin.
PII_COLLECTION = "water_well_field_operations"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""


@dataclass
class Smoke:
    client: httpx.Client
    base_url: str
    token: str | None
    api_key: str | None
    results: list[Result] = field(default_factory=list)

    # -- plumbing ----------------------------------------------------------
    def record(self, name: str, status: str, detail: str = "") -> Result:
        result = Result(name, status, detail)
        self.results.append(result)
        line = f"{status:4}  {name}"
        print(f"{line}\n      {detail}" if detail else line, flush=True)
        return result

    def check(self, name: str, fn: Callable[[], str | None]) -> None:
        """Run one check. Return None to pass, or a string saying what failed."""
        try:
            problem = fn()
        except httpx.HTTPError as err:
            self.record(name, FAIL, f"request failed: {err!r}")
            return
        except Exception as err:  # noqa: BLE001 - a smoke test reports, never raises
            self.record(name, FAIL, f"unexpected error: {err!r}")
            return
        self.record(name, PASS if problem is None else FAIL, problem or "")

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.client.get(self.url(path), **kwargs)

    @staticmethod
    def _expected(response: httpx.Response, *codes: int) -> str | None:
        if response.status_code in codes:
            return None
        wanted = " or ".join(str(code) for code in codes)
        body = response.text[:200].replace("\n", " ")
        return f"expected {wanted}, got {response.status_code}: {body}"

    # -- public ------------------------------------------------------------
    def check_health(self, expect_version: str | None) -> None:
        def run() -> str | None:
            response = self.get("/health")
            if problem := self._expected(response, 200):
                return problem
            body = response.json()
            # A 200 means the database answered too: the route pings PostGIS
            # and degrades to 503, so anything else here is a contract change.
            if body.get("status") != "ok" or body.get("db") != "ok":
                return f"unhealthy: {body}"
            version = body.get("version")
            if expect_version and version != expect_version:
                return f"version is {version!r}, expected {expect_version!r}"
            # Worth seeing on every run: it says which build answered, which is
            # the first thing in doubt when a release smoke test surprises you.
            print(f"      version {version}", flush=True)
            return None

        self.check("GET /health", run)

    def check_docs(self) -> None:
        def run() -> str | None:
            response = self.get("/docs")
            if problem := self._expected(response, 200):
                return problem
            if "swagger" not in response.text.lower():
                return "body does not look like Swagger UI"
            return None

        self.check("GET /docs", run)

    def check_public_collections(self) -> None:
        def run() -> str | None:
            response = self.get("/ogcapi/collections", params={"f": "json"})
            if problem := self._expected(response, 200):
                return problem
            ids = {c.get("id") for c in response.json().get("collections", [])}
            if not ids:
                return "no collections listed"
            missing = [c for c in EXPECTED_PUBLIC_COLLECTIONS if c not in ids]
            if missing:
                return f"missing collections: {', '.join(missing)} (saw {len(ids)})"
            return None

        self.check("GET /ogcapi/collections", run)

    def check_pii_collection_is_not_public(self) -> None:
        """The internal layer must have no public twin. See CLAUDE.md."""

        def run() -> str | None:
            response = self.get("/ogcapi/collections", params={"f": "json"})
            if problem := self._expected(response, 200):
                return problem
            ids = {c.get("id") for c in response.json().get("collections", [])}
            if PII_COLLECTION in ids:
                return (
                    f"{PII_COLLECTION} is on the PUBLIC mount -- it carries "
                    "landowner contact details and must never be published"
                )
            items = self.get(f"/ogcapi/collections/{PII_COLLECTION}/items")
            if items.status_code == 200:
                return f"/ogcapi/collections/{PII_COLLECTION}/items answered 200"
            return None

        self.check(f"{PII_COLLECTION} absent from public mount", run)

    # -- internal mount ----------------------------------------------------
    def check_internal_requires_a_credential(self) -> None:
        def run() -> str | None:
            response = self.get("/ogcapi-internal/collections")
            if problem := self._expected(response, 401):
                return problem
            # The challenge is what makes ArcGIS Pro and QGIS prompt rather
            # than fail silently.
            if "www-authenticate" not in {k.lower() for k in response.headers}:
                return "401 carried no WWW-Authenticate challenge"
            return None

        self.check("GET /ogcapi-internal/collections (anonymous) -> 401", run)

    def check_internal_rejects_a_bad_credential(self) -> None:
        def run() -> str | None:
            response = self.get(
                "/ogcapi-internal/collections",
                headers={"Authorization": "Bearer not-a-real-credential"},
            )
            return self._expected(response, 401)

        self.check("GET /ogcapi-internal/collections (bad credential) -> 401", run)

    def _internal_collections_with(self, name: str, **request: dict) -> None:
        def run() -> str | None:
            response = self.get("/ogcapi-internal/collections", **request)
            if problem := self._expected(response, 200):
                return problem
            ids = {c.get("id") for c in response.json().get("collections", [])}
            if PII_COLLECTION not in ids:
                return f"{PII_COLLECTION} not listed (saw {len(ids)} collections)"
            return None

        self.check(name, run)

    def check_internal_with_token(self) -> None:
        if not self.token:
            self.record(
                "GET /ogcapi-internal/collections (Authentik bearer)",
                SKIP,
                "no --token given",
            )
            return
        self._internal_collections_with(
            "GET /ogcapi-internal/collections (Authentik bearer)",
            headers={"Authorization": f"Bearer {self.token}"},
            params={"f": "json"},
        )

    def check_internal_with_api_key(self) -> None:
        if not self.api_key:
            for transport in ("bearer", "basic", "?token="):
                self.record(
                    f"GET /ogcapi-internal/collections (API key, {transport})",
                    SKIP,
                    "no --api-key given",
                )
            return

        self._internal_collections_with(
            "GET /ogcapi-internal/collections (API key, bearer)",
            headers={"Authorization": f"Bearer {self.api_key}"},
            params={"f": "json"},
        )
        # ArcGIS Pro can only send Basic; the username half is ignored.
        self._internal_collections_with(
            "GET /ogcapi-internal/collections (API key, basic)",
            auth=("apikey", self.api_key),
            params={"f": "json"},
        )
        # ArcGIS Pro's "Custom request parameters".
        self._internal_collections_with(
            "GET /ogcapi-internal/collections (API key, ?token=)",
            params={"token": self.api_key, "f": "json"},
        )

    def check_pii_items(self) -> None:
        credential = self.bearer()
        name = f"GET /ogcapi-internal/collections/{PII_COLLECTION}/items?limit=1"
        if not credential:
            self.record(name, SKIP, "no --token or --api-key given")
        else:

            def run() -> str | None:
                response = self.get(
                    f"/ogcapi-internal/collections/{PII_COLLECTION}/items",
                    headers={"Authorization": f"Bearer {credential}"},
                    params={"limit": 1, "f": "json"},
                )
                if problem := self._expected(response, 200):
                    return problem
                features = response.json().get("features")
                if features is None:
                    return "response carried no 'features'"
                if not features:
                    return "returned zero features -- the layer looks empty"
                return None

            self.check(name, run)

        def anonymous() -> str | None:
            response = self.get(
                f"/ogcapi-internal/collections/{PII_COLLECTION}/items",
                params={"limit": 1},
            )
            return self._expected(response, 401)

        self.check(f"{PII_COLLECTION}/items (anonymous) -> 401", anonymous)

    # -- API key routes (read-only) ----------------------------------------
    def check_api_key_listing(self) -> None:
        """
        List the caller's keys. Read-only on purpose: minting one writes a row
        that outlives the run, and revoking it writes another. The key this
        script authenticates with is the one in .env, not one it issues.
        """
        name = "GET /api_key lists your keys"
        if not self.token:
            self.record(name, SKIP, "no --token given (the route needs a JWT)")
            return

        def run() -> str | None:
            response = self.get(
                "/api_key", headers={"Authorization": f"Bearer {self.token}"}
            )
            if problem := self._expected(response, 200):
                return problem
            body = response.json()
            if not isinstance(body, list):
                return f"expected a list of keys, got {type(body).__name__}"
            # A token is never echoed back by this route -- only digests are
            # stored, so a key appearing here would be a leak.
            if any("token" in key for key in body):
                return "a listed key carried a token field"
            return None

        self.check(name, run)

    def bearer(self) -> str | None:
        """Whichever credential is available; the mount accepts either."""
        return self.token or self.api_key


def run_all(smoke: Smoke, expect_version: str | None) -> None:
    print(f"Smoke testing {smoke.base_url}\n", flush=True)
    smoke.check_health(expect_version)
    smoke.check_docs()
    smoke.check_public_collections()
    smoke.check_pii_collection_is_not_public()
    smoke.check_internal_requires_a_credential()
    smoke.check_internal_rejects_a_bad_credential()
    smoke.check_internal_with_token()
    smoke.check_internal_with_api_key()
    smoke.check_pii_items()
    smoke.check_api_key_listing()


def summarize(results: Iterable[Result], strict: bool) -> int:
    results = list(results)
    counts = {status: 0 for status in (PASS, FAIL, SKIP)}
    for result in results:
        counts[result.status] += 1

    print(
        f"\n{counts[PASS]} passed, {counts[FAIL]} failed, {counts[SKIP]} skipped",
        flush=True,
    )
    for result in results:
        if result.status == FAIL:
            print(f"  FAIL  {result.name}: {result.detail}", flush=True)

    if counts[FAIL]:
        return 1
    if strict and counts[SKIP]:
        print("  --strict: skipped checks count as failures", flush=True)
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test a deployed Ocotillo API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Credentials may also come from the environment: "
            "SMOKE_BASE_URL, SMOKE_TOKEN, SMOKE_API_KEY."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_BASE_URL"),
        help="e.g. https://ocotillo-api-staging.newmexicowaterdata.org",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SMOKE_TOKEN"),
        help="Authentik access token carrying OGC.Internal",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SMOKE_API_KEY"),
        help="A static or user-issued API key for the internal mount",
    )
    parser.add_argument(
        "--expect-version",
        help="Fail unless /health reports this version, e.g. 1.4.0",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="dotenv file to read API_KEY from when --api-key is not given",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat skipped checks as failures",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    if not args.base_url:
        parser.error("--base-url is required (or set SMOKE_BASE_URL)")
    args.base_url = args.base_url.rstrip("/")
    args.api_key = args.api_key or _api_key_from_env_file(args.env_file)
    return args


def _api_key_from_env_file(env_file: str) -> str | None:
    """
    `API_KEY` out of the dotenv file, if there is one.

    override=False matches db/engine.py: a value already exported wins over the
    file, so SMOKE_API_KEY and a CI secret both work without editing .env.
    """
    path = Path(env_file)
    if not path.is_file():
        return None
    load_dotenv(path, override=False)
    return os.environ.get("API_KEY") or None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # follow_redirects: /docs and the OGC mounts answer on both spellings of
    # their path depending on the deployment's trailing-slash handling.
    with httpx.Client(timeout=args.timeout, follow_redirects=True) as client:
        smoke = Smoke(
            client=client,
            base_url=args.base_url,
            token=args.token,
            api_key=args.api_key,
        )
        run_all(smoke, args.expect_version)
        return summarize(smoke.results, args.strict)


if __name__ == "__main__":
    sys.exit(main())

# ============= EOF =============================================
