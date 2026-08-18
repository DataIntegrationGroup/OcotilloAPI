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
GCS raw-zone conventions.

Every source writes date-partitioned parquet under one bucket per environment,
so a replay backfill can select an exact window by prefix without reading the
files.

``services/gcs_helper.py`` serves user uploads from ``GCS_BUCKET_NAME``.
Ingestion deliberately reads a different variable: sharing it would let a
misconfigured deployment write raw vendor payloads into the uploads bucket.
"""

BUCKET_ENV_VAR = "INGESTION_GCS_BUCKET"
"""Environment variable naming the raw-zone bucket. Never ``GCS_BUCKET_NAME``."""

RAW_LAYOUT = "{table_name}/year={YYYY}/month={MM}/day={DD}/{load_id}.{file_id}.{ext}"
"""dlt filesystem layout for the raw zone."""


def raw_zone_bucket() -> str:
    """Name of the raw-zone bucket for this environment.

    Raises rather than defaulting. A wrong bucket name is not a condition worth
    guessing through: the failure would be a run that reports success while
    writing nowhere useful, or worse, into a bucket that belongs to something
    else.
    """
    import os

    bucket = os.environ.get(BUCKET_ENV_VAR, "").strip()
    if not bucket:
        raise RuntimeError(
            f"{BUCKET_ENV_VAR} is not set. The ingestion raw zone has no default; "
            "set it on the Dagster+ code location to the bucket Terraform "
            "created (see automated_ingestion/iac)."
        )
    if bucket == os.environ.get("GCS_BUCKET_NAME", "").strip():
        raise RuntimeError(
            f"{BUCKET_ENV_VAR} points at GCS_BUCKET_NAME, the API's user-upload "
            "bucket. Raw vendor payloads must not be written there."
        )
    return bucket


# ============= EOF =============================================
