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
Credential materialization for a runtime with no metadata server.

The failure this prevents is not subtle -- DefaultCredentialsError -- but it
only appears in Serverless, so the tests stand in for a deployment.
"""

import json
import os

import pytest

from automated_ingestion.shared import credentials
from automated_ingestion.shared.credentials import (
    CREDENTIALS_ENV_VAR,
    ensure_application_default_credentials,
)

KEY = {"type": "service_account", "project_id": "waterdatainitiative-271000"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(credentials, "_written_path", None)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv(CREDENTIALS_ENV_VAR, raising=False)


def test_existing_credentials_are_left_alone(monkeypatch):
    # A developer's gcloud login must not be shadowed by a key in the
    # environment; whatever is already configured wins.
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/existing/adc.json")
    monkeypatch.setenv(CREDENTIALS_ENV_VAR, json.dumps(KEY))
    assert ensure_application_default_credentials() == "/existing/adc.json"


def test_no_key_configured_is_not_an_error(monkeypatch):
    # Locally this is normal -- google.auth finds its own credentials. In
    # Serverless it fails later, loudly, which is the correct outcome.
    assert ensure_application_default_credentials() is None
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ


def test_key_is_written_and_pointed_at(monkeypatch):
    monkeypatch.setenv(CREDENTIALS_ENV_VAR, json.dumps(KEY))
    path = ensure_application_default_credentials()
    assert path and os.path.exists(path)
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == path
    with open(path) as fh:
        assert json.load(fh) == KEY


def test_key_file_is_not_world_readable(monkeypatch):
    monkeypatch.setenv(CREDENTIALS_ENV_VAR, json.dumps(KEY))
    path = ensure_application_default_credentials()
    assert oct(os.stat(path).st_mode)[-3:] == "600"


def test_repeated_calls_write_once(monkeypatch):
    monkeypatch.setenv(CREDENTIALS_ENV_VAR, json.dumps(KEY))
    first = ensure_application_default_credentials()
    assert ensure_application_default_credentials() == first


def test_a_path_instead_of_a_key_is_rejected(monkeypatch):
    # Setting the variable to a filename is the obvious mistake, and it would
    # otherwise fail much later inside google.auth.
    monkeypatch.setenv(CREDENTIALS_ENV_VAR, "/path/to/key.json")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        ensure_application_default_credentials()


# ============= EOF =============================================
