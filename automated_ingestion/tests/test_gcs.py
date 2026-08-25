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
Bucket resolution refuses to guess.

The uploads-bucket check is the one worth testing: `services/gcs_helper.py`
already uses GCS_BUCKET_NAME, and the two variables being confused is a
configuration mistake that would otherwise succeed quietly.
"""

import pytest

from automated_ingestion.shared.gcs import BUCKET_ENV_VAR, RAW_LAYOUT, raw_zone_bucket


def test_returns_the_configured_bucket(monkeypatch):
    monkeypatch.setenv(BUCKET_ENV_VAR, "ocotillo-ingestion-staging")
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    assert raw_zone_bucket() == "ocotillo-ingestion-staging"


def test_unset_bucket_raises(monkeypatch):
    monkeypatch.delenv(BUCKET_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match=BUCKET_ENV_VAR):
        raw_zone_bucket()


def test_blank_bucket_raises(monkeypatch):
    monkeypatch.setenv(BUCKET_ENV_VAR, "   ")
    with pytest.raises(RuntimeError, match=BUCKET_ENV_VAR):
        raw_zone_bucket()


def test_uploads_bucket_is_rejected(monkeypatch):
    monkeypatch.setenv(BUCKET_ENV_VAR, "ocotillo-uploads")
    monkeypatch.setenv("GCS_BUCKET_NAME", "ocotillo-uploads")
    with pytest.raises(RuntimeError, match="user-upload"):
        raw_zone_bucket()


def test_layout_partitions_by_date():
    # Mode B replay selects a window by prefix, which only works if the date
    # is in the path rather than inside the file.
    assert "year={YYYY}" in RAW_LAYOUT
    assert "month={MM}" in RAW_LAYOUT
    assert "day={DD}" in RAW_LAYOUT


def test_pipeline_name_follows_the_bucket(monkeypatch):
    # The name and the destination must not be able to disagree. They did once:
    # a pipeline called san_acacia_staging wrote to the production bucket,
    # because the name came from an absent run tag and the bucket from the
    # environment.
    monkeypatch.setenv(BUCKET_ENV_VAR, "ocotillo-ingestion-production")
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    monkeypatch.setenv("INGESTION_GCP_CREDENTIALS_JSON", "")

    from automated_ingestion.sources.san_acacia.dlt_pipeline import build_pipeline

    pipeline = build_pipeline()
    assert "ocotillo-ingestion-production" in pipeline.pipeline_name


# ============= EOF =============================================
