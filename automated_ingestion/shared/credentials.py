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
Application Default Credentials for a runtime that has none.

Dagster+ Serverless runs outside GCP, so there is no metadata server to supply
credentials. Anything reaching Google -- the Cloud SQL connector for the loader,
gcsfs for the raw zone -- calls ``google.auth.default()`` and fails with
``DefaultCredentialsError`` unless something has put credentials on disk first.

The service account key therefore travels as a Dagster+ secret and is written to
a file here, because ``GOOGLE_APPLICATION_CREDENTIALS`` names a path rather than
holding a value. The file lands in the process's temporary directory, which the
container discards when the run ends.
"""

import json
import os
import tempfile

CREDENTIALS_ENV_VAR = "INGESTION_GCP_CREDENTIALS_JSON"
"""Service account key JSON, as a Dagster+ secret. Never committed."""

_ADC_ENV_VAR = "GOOGLE_APPLICATION_CREDENTIALS"

_written_path: str | None = None


def ensure_application_default_credentials() -> str | None:
    """Materialize ADC from the environment, returning the path if written.

    Idempotent, and does nothing when credentials already exist -- locally that
    means a developer's gcloud login is used as-is rather than being shadowed.
    """
    global _written_path

    existing = os.environ.get(_ADC_ENV_VAR, "").strip()
    if existing:
        return existing
    if _written_path is not None:
        return _written_path

    raw = os.environ.get(CREDENTIALS_ENV_VAR, "").strip()
    if not raw:
        # No key configured. Leave google.auth to its own discovery, which
        # succeeds on a developer machine and fails loudly in Serverless -- the
        # right outcome in both cases.
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{CREDENTIALS_ENV_VAR} is set but is not valid JSON. It must hold the "
            "service account key itself, not a path to one."
        ) from exc

    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="ingestion-adc-", delete=False
    )
    with handle as fh:
        json.dump(parsed, fh)
    os.chmod(handle.name, 0o600)

    os.environ[_ADC_ENV_VAR] = handle.name
    _written_path = handle.name
    return handle.name


# ============= EOF =============================================
