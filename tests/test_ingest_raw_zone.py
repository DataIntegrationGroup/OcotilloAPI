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
"""Tests for the dlt raw zone behind the `oco` ingests
(services/ingest_raw_zone.py)."""

from datetime import datetime
from unittest import mock

import fsspec
import pytest

from services.chemistry_field_sheet import SheetTable
from services.ingest_raw_zone import (
    BUCKET_ENV_VAR,
    LOCAL_DIR_ENV_VAR,
    RawZoneError,
    archive_tables,
    list_snapshots,
    raw_zone_url,
    read_snapshot,
)

DATASET = "test_field_sheet"


@pytest.fixture()
def raw_url(tmp_path):
    """A raw zone on disk, so tests never touch a bucket."""
    return (tmp_path / "raw").resolve().as_uri()


@pytest.fixture()
def pipelines_dir(tmp_path):
    """Keep dlt's working state out of the developer's ~/.dlt."""
    return str(tmp_path / "dlt-pipelines")


def _table(title="ChemistrySampleInfo", rows=None):
    header = ["WellPointID", "CollectionDate", "pHf"]
    rows = (
        rows
        if rows is not None
        else [
            {
                "WellPointID": "RA-116",
                "CollectionDate": datetime(2025, 6, 10, 12, 5),
                "pHf": 6.94,
                SheetTable.ROW_NUMBER_KEY: 2,
            }
        ]
    )
    return SheetTable(title=title, header=header, rows=rows)


def _archive(tables, raw_url, pipelines_dir, label="test"):
    return archive_tables(
        tables,
        dataset=DATASET,
        source_label=label,
        raw_url=raw_url,
        pipelines_dir=pipelines_dir,
    )


# --- where the archive lives ---------------------------------------------------


def test_raw_zone_url_prefers_the_bucket(monkeypatch):
    monkeypatch.setenv(BUCKET_ENV_VAR, "nmbgmr-raw")
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    assert raw_zone_url() == "gs://nmbgmr-raw/oco-raw"


def test_raw_zone_url_refuses_the_user_upload_bucket(monkeypatch):
    """Source payloads must never land in the bucket serving user uploads."""
    monkeypatch.setenv(BUCKET_ENV_VAR, "ocotillo")
    monkeypatch.setenv("GCS_BUCKET_NAME", "ocotillo")
    with pytest.raises(RawZoneError) as exc:
        raw_zone_url()
    assert "user-upload bucket" in str(exc.value)


@pytest.mark.parametrize(
    "explicit",
    ["gs://ocotillo/oco-raw", "gs://ocotillo", "gs://ocotillo/nested/prefix"],
)
def test_raw_url_cannot_route_around_the_upload_bucket_guard(monkeypatch, explicit):
    """--raw-url is exactly what someone reaches for when the default is wrong."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "ocotillo")
    with pytest.raises(RawZoneError) as exc:
        raw_zone_url(explicit)
    assert "user-upload bucket" in str(exc.value)


def test_raw_url_to_another_bucket_is_fine(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "ocotillo")
    assert raw_zone_url("gs://nmbgmr-raw/oco-raw") == "gs://nmbgmr-raw/oco-raw"


def test_a_local_raw_url_is_not_checked_against_the_bucket(monkeypatch, tmp_path):
    monkeypatch.setenv("GCS_BUCKET_NAME", "ocotillo")
    url = tmp_path.resolve().as_uri()
    assert raw_zone_url(url) == url


def test_reading_a_snapshot_lists_only_that_snapshot(raw_url, pipelines_dir):
    """A read must not page through every snapshot ever archived."""
    _archive([_table()], raw_url, pipelines_dir)
    wanted = _archive([_table(title="FieldParameters")], raw_url, pipelines_dir)

    fs, root = fsspec.core.url_to_fs(raw_url)
    seen = []
    original = fs.glob

    def recording_glob(pattern, **kwargs):
        seen.append(pattern)
        return original(pattern, **kwargs)

    with mock.patch.object(fs.__class__, "glob", side_effect=recording_glob):
        read_snapshot(DATASET, wanted.load_id, raw_url=raw_url)

    assert seen, "read_snapshot did not glob at all"
    assert all(wanted.load_id in pattern for pattern in seen), seen


def test_raw_zone_url_falls_back_to_a_local_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(BUCKET_ENV_VAR, raising=False)
    monkeypatch.setenv(LOCAL_DIR_ENV_VAR, str(tmp_path))
    assert raw_zone_url().startswith("file://")


def test_raw_zone_url_refuses_to_guess(monkeypatch):
    """Writing nowhere useful while reporting success is the worse failure."""
    monkeypatch.delenv(BUCKET_ENV_VAR, raising=False)
    monkeypatch.delenv(LOCAL_DIR_ENV_VAR, raising=False)
    with pytest.raises(RawZoneError) as exc:
        raw_zone_url()
    assert "--no-raw" in str(exc.value)


# --- round trip ----------------------------------------------------------------


def test_archived_rows_come_back_unchanged(raw_url, pipelines_dir):
    extract = _archive([_table()], raw_url, pipelines_dir)
    assert extract.total_rows == 1

    (table,) = read_snapshot(DATASET, extract.load_id, raw_url=raw_url)

    assert table.title == "ChemistrySampleInfo"
    assert table.header == ["WellPointID", "CollectionDate", "pHf"]
    (row,) = table.rows
    assert row["WellPointID"] == "RA-116"
    assert row["pHf"] == 6.94
    assert table.row_number(row) == 2
    # A date cell round-trips as ISO text, which is what the mapping layer
    # parses either way.
    assert row["CollectionDate"] == "2025-06-10T12:05:00"


def test_headings_survive_however_they_are_spelled(raw_url, pipelines_dir):
    """The archive keeps headings as typed; it is not a normalized schema."""
    table = SheetTable(
        title="FieldParameters",
        header=["SamplePointID", "T (C)", "CF (uS/cm)", "Discharge rate (gpm)"],
        rows=[
            {
                "SamplePointID": "RA-116A",
                "T (C)": 15.7,
                "CF (uS/cm)": 783.0,
                "Discharge rate (gpm)": None,
                SheetTable.ROW_NUMBER_KEY: 2,
            }
        ],
    )
    extract = _archive([table], raw_url, pipelines_dir)

    (restored,) = read_snapshot(DATASET, extract.load_id, raw_url=raw_url)
    assert restored.rows[0]["CF (uS/cm)"] == 783.0
    assert restored.rows[0]["Discharge rate (gpm)"] is None


def test_two_tabs_archive_and_return_separately(raw_url, pipelines_dir):
    tables = [_table(), _table(title="FieldParameters")]
    extract = _archive(tables, raw_url, pipelines_dir)

    restored = {
        t.title: t for t in read_snapshot(DATASET, extract.load_id, raw_url=raw_url)
    }
    assert set(restored) == {"ChemistrySampleInfo", "FieldParameters"}
    assert extract.row_counts == {"ChemistrySampleInfo": 1, "FieldParameters": 1}


def test_a_later_run_does_not_disturb_an_earlier_snapshot(raw_url, pipelines_dir):
    """The whole point of the archive: what the source said, when it said it."""
    first = _archive([_table()], raw_url, pipelines_dir)
    changed = _table(
        rows=[
            {
                "WellPointID": "RA-116",
                "CollectionDate": "2025-06-10T12:05:00",
                "pHf": 9.99,
                SheetTable.ROW_NUMBER_KEY: 2,
            }
        ]
    )
    second = _archive([changed], raw_url, pipelines_dir)

    assert first.load_id != second.load_id
    (old_table,) = read_snapshot(DATASET, first.load_id, raw_url=raw_url)
    (new_table,) = read_snapshot(DATASET, second.load_id, raw_url=raw_url)
    assert old_table.rows[0]["pHf"] == 6.94
    assert new_table.rows[0]["pHf"] == 9.99


def test_latest_snapshot_is_the_default(raw_url, pipelines_dir):
    _archive([_table()], raw_url, pipelines_dir)
    second = _archive([_table(title="FieldParameters")], raw_url, pipelines_dir)

    restored = read_snapshot(DATASET, raw_url=raw_url)
    assert [t.title for t in restored] == ["FieldParameters"]
    assert list_snapshots(DATASET, raw_url=raw_url)[-1] == second.load_id


def test_reading_an_unknown_snapshot_names_the_ones_held(raw_url, pipelines_dir):
    extract = _archive([_table()], raw_url, pipelines_dir)
    with pytest.raises(RawZoneError) as exc:
        read_snapshot(DATASET, "no-such-load", raw_url=raw_url)
    assert extract.load_id in str(exc.value)


def test_reading_an_empty_raw_zone_explains_itself(raw_url):
    with pytest.raises(RawZoneError) as exc:
        read_snapshot(DATASET, raw_url=raw_url)
    assert "No archived snapshot" in str(exc.value)


def test_archiving_nothing_is_refused(raw_url, pipelines_dir):
    with pytest.raises(RawZoneError):
        _archive([SheetTable(title="Empty")], raw_url, pipelines_dir)


# ============= EOF =============================================
