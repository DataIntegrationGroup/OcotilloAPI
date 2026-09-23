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

Read-only by default. The API-key lifecycle writes rows to the target's
database, so it runs only under ``--write``.

    uv run python -m scripts.smoke_test --base-url https://<host>

    # with credentials (either or both)
    uv run python -m scripts.smoke_test --base-url https://<host> \\
        --token "$AUTHENTIK_ACCESS_TOKEN" --api-key "$INTERNAL_OGC_KEY"

    # include the mint/use/revoke cycle -- writes to the target database
    uv run python -m scripts.smoke_test --base-url https://<host> \\
        --token "$AUTHENTIK_ACCESS_TOKEN" --write

Exit status is 0 when nothing failed, 1 when anything did. Checks whose
credentials were not supplied are SKIPped, which is not a failure unless
``--strict`` is passed -- so an unattended run that quietly tested nothing but
``/health`` cannot report success.

A check needs a *bearer* credential; the static keys and user-issued keys are
interchangeable there. ``--api-key`` is additionally exercised through the two
transports the desktop GIS clients need (HTTP Basic, and ``?token=``), because
those paths are what ArcGIS Pro and QGIS actually use and they are easy to
break without noticing. See docs/internal-ogc-desktop-gis.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable

import httpx

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
    write: bool
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

    # -- API key lifecycle -------------------------------------------------
    def check_api_key_lifecycle(self) -> None:
        """Mint a key, use it, revoke it, and prove it is dead afterwards."""
        steps = (
            "POST /api_key mints a key",
            "GET /api_key lists the new key",
            "minted key reaches /ogcapi-internal",
            "DELETE /api_key/{id} revokes it",
            "revoked key is refused on the next request",
        )
        if not self.token:
            for step in steps:
                self.record(step, SKIP, "no --token given")
            return
        if not self.write:
            for step in steps:
                self.record(step, SKIP, "writes to the database; pass --write")
            return

        auth = {"Authorization": f"Bearer {self.token}"}
        key_id: int | None = None
        token: str | None = None

        def mint() -> str | None:
            nonlocal key_id, token
            response = self.client.post(
                self.url("/api_key"),
                headers=auth,
                json={"name": "smoke test", "lifetime_days": 1},
            )
            if problem := self._expected(response, 201):
                return problem
            body = response.json()
            key_id, token = body.get("id"), body.get("token")
            if not token:
                return "response carried no token"
            if key_id is None:
                return "response carried no id"
            return None

        self.check(steps[0], mint)
        if key_id is None or token is None:
            for step in steps[1:]:
                self.record(step, SKIP, "no key was minted")
            return

        def listed() -> str | None:
            response = self.get("/api_key", headers=auth)
            if problem := self._expected(response, 200):
                return problem
            keys = {k.get("id") for k in response.json()}
            if key_id not in keys:
                return f"key {key_id} missing from the list"
            return None

        def usable() -> str | None:
            response = self.get(
                "/ogcapi-internal/collections",
                headers={"Authorization": f"Bearer {token}"},
                params={"f": "json"},
            )
            return self._expected(response, 200)

        def revoke() -> str | None:
            response = self.client.delete(self.url(f"/api_key/{key_id}"), headers=auth)
            return self._expected(response, 204)

        def dead() -> str | None:
            # Revocation is checked per request, so the very next one fails --
            # no redeploy, no cache to wait out.
            response = self.get(
                "/ogcapi-internal/collections",
                headers={"Authorization": f"Bearer {token}"},
            )
            return self._expected(response, 401)

        self.check(steps[1], listed)
        self.check(steps[2], usable)
        self.check(steps[3], revoke)
        self.check(steps[4], dead)

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
    smoke.check_api_key_lifecycle()


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
        "--write",
        action="store_true",
        help="Run the API-key lifecycle, which writes rows to the target database",
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
    return args


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
            write=args.write,
        )
        run_all(smoke, args.expect_version)
        return summarize(smoke.results, args.strict)


if __name__ == "__main__":
    sys.exit(main())

# ============= EOF =============================================
