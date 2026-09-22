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
Repo-wide test isolation: guarantee the suite runs without live Google Cloud auth.

BDMS-550. The pipeline reaches Google in three places -- the Cloud SQL IAM login
in ``db.engine``, the Drive sync in ``services.chemistry_drive``, and alembic's
migration env -- each of which calls ``google.auth.default()``. That lookup hits
the metadata server / a key on disk and raises ``DefaultCredentialsError`` on any
machine with no GCP credentials (CI, a bare laptop). The tests stand in for a
deployment, so they must never need real creds to run.

This fixture patches ``google.auth.default`` at its source, which also catches
gcsfs and the Cloud SQL connector because they call it internally at runtime. It
is *conditional*: if a developer has already put legitimate credentials on disk
(``GOOGLE_APPLICATION_CREDENTIALS``) or handed a key through
``INGESTION_GCP_CREDENTIALS_JSON``, those win untouched -- only when neither is
set do we inject fakes, so local ``gcloud auth application-default login`` flows
are never shadowed.

Scope is the whole repo: a root ``conftest.py`` applies to both ``tests/`` and
``automated_ingestion/tests/``, whereas a fixture in either directory alone would
leave the other half uncovered.
"""

import json
import os
import tempfile

import pytest

# A credential is "real" when one of the project's own mechanisms already points
# at it: an ADC file on disk, or a service-account key handed in as a secret.
_REAL_CRED_ENV_VARS = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "INGESTION_GCP_CREDENTIALS_JSON",
)


def _has_real_credentials() -> bool:
    return any(os.environ.get(name, "").strip() for name in _REAL_CRED_ENV_VARS)


class FakeCredentials:
    """Minimal stand-in for ``google.auth.credentials.Credentials``.

    The only caller in the repo is ``db.engine.get_iam_login_token``, which does
    ``creds.with_scopes(...)`` then ``creds.refresh(Request())`` and reads
    ``creds.token``. gcsfs / the connector only need ``default()`` to return a
    truthy first tuple element, which this satisfies.
    """

    def __init__(self, token: str = "offline-fake-token") -> None:
        self.token = token

    def with_scopes(self, scopes=None, additional_scopes=None, **kwargs):
        return self

    def refresh(self, request=None) -> None:
        self.token = "offline-fake-token"


@pytest.fixture(autouse=True)
def _offline_google_auth(monkeypatch):
    """Return fake GCP credentials whenever none are legitimately configured."""
    # Single yield point: a generator fixture must always yield, so setup is
    # conditional but the yield itself is not. When real creds are present we do
    # nothing and let google.auth discover them normally.
    if not _has_real_credentials():
        # Point GOOGLE_APPLICATION_CREDENTIALS at a real file path so any code
        # that reads the env var directly (rather than calling default()) still
        # finds a plausible key on disk. The contents need not validate --
        # nothing parses it while default() is patched below.
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="bdms550-adc-", delete=False
        )
        with handle as fh:
            json.dump(
                {"type": "service_account", "project_id": "waterdatainitiative-offline"},
                fh,
            )
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", handle.name)

        import google.auth

        def _fake_default(*args, **kwargs):
            return FakeCredentials(), None

        # Patch at the module so both ``google.auth.default(...)`` and a later
        # function-level ``from google.auth import default`` resolve to the fake.
        monkeypatch.setattr(google.auth, "default", _fake_default, raising=True)

    yield


# ============= EOF =============================================
