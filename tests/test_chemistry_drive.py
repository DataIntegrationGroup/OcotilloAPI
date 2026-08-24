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
"""Tests for the Drive-polling chemistry sync (services/chemistry_drive.py)."""

import io
import sys
import types
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from sqlalchemy import delete

from db.engine import session_ctx
from db.nma_legacy import NMA_Chemistry_SampleInfo
from services import chemistry_drive
from services.chemistry_drive import (
    ChemistryDriveConfigError,
    assert_folder_accessible,
    load_manifest,
    save_manifest,
    sync_and_ingest,
)

LIMS_HEADER = [
    "Param",
    "Results_Units",
    "Dilution",
    "AnalysisTime",
    "SampleNumber",
    "CustomerSampleNumber",
    "SamplePointID",
    "Method",
    "Test",
    "ReportedND",
    "LowerLimit",
    "SampleDate",
]


def _workbook_bytes(param="calcium", value="12.5", pointid="Test Well"):
    wb = Workbook()
    ws = wb.active
    ws.append(LIMS_HEADER)
    ws.append(
        [
            param,
            "mg/L",
            1,
            "2024-06-15",
            "LAB-1",
            pointid,
            pointid,
            "EPA 200.7",
            "Major",
            value,
            0.01,
            "2024-06-01",
        ]
    )
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class FakeBlob:
    def __init__(self, store, name):
        self._store = store
        self._name = name

    def exists(self):
        return self._name in self._store

    def download_as_text(self):
        return self._store[self._name]

    def upload_from_string(self, data, content_type=None):
        self._store[self._name] = data


class FakeBucket:
    def __init__(self):
        self.store = {}

    def blob(self, name):
        return FakeBlob(self.store, name)

    def list_blobs(self, prefix=""):
        return [
            SimpleNamespace(name=name)
            for name in sorted(self.store)
            if name.startswith(prefix)
        ]


@pytest.fixture()
def fake_bucket():
    return FakeBucket()


@pytest.fixture()
def _cleanup_chemistry():
    yield
    with session_ctx() as session:
        session.execute(
            delete(NMA_Chemistry_SampleInfo).where(
                NMA_Chemistry_SampleInfo.nma_wclab_id.like("LAB-%")
            )
        )
        session.commit()


def _stub_drive(monkeypatch, files: list[dict], contents: dict[str, bytes]):
    monkeypatch.setattr(
        chemistry_drive, "list_drive_xlsx", lambda folder_id, service=None: files
    )

    def _download(file_id, service=None):
        return contents[file_id]

    monkeypatch.setattr(chemistry_drive, "download_drive_file", _download)


# ------------------------- manifest tests ------------------------------------


def test_manifest_roundtrip(fake_bucket):
    assert load_manifest(fake_bucket) == {}
    save_manifest({"F1": {"status": "success"}}, fake_bucket)
    assert load_manifest(fake_bucket) == {"F1": {"status": "success"}}


def test_manifest_path_scoped_to_database(monkeypatch):
    """The manifest key follows POSTGRES_DB so one database cannot mask another."""
    monkeypatch.delenv("CHEMISTRY_INGEST_MANIFEST_PATH", raising=False)

    monkeypatch.setenv("POSTGRES_DB", "ocotillo-staging")
    assert (
        chemistry_drive._manifest_path()
        == "chemistry-ingest/manifest.ocotillo-staging.json"
    )

    # Underscores and case are slugged so the key is a safe object name.
    monkeypatch.setenv("POSTGRES_DB", "Ocotillo_Prod_Copy")
    assert (
        chemistry_drive._manifest_path()
        == "chemistry-ingest/manifest.ocotillo-prod-copy.json"
    )


def test_manifest_path_override_wins(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "ocotillo-staging")
    monkeypatch.setenv("CHEMISTRY_INGEST_MANIFEST_PATH", "custom/manifest.json")
    assert chemistry_drive._manifest_path() == "custom/manifest.json"


def test_manifest_overview_merges_databases(monkeypatch, fake_bucket):
    """The cross-database view answers 'has this workbook reached staging?'."""
    monkeypatch.delenv("CHEMISTRY_INGEST_MANIFEST_PATH", raising=False)

    monkeypatch.setenv("POSTGRES_DB", "ocotillo_prod_copy")
    save_manifest(
        {
            "F1": {"name": "wells.xlsx", "status": "success", "rows_imported": 12},
            "F2": {"name": "other.xlsx", "status": "failed", "error": "no Thing"},
        },
        fake_bucket,
    )

    monkeypatch.setenv("POSTGRES_DB", "ocotillo-staging")
    save_manifest(
        {"F1": {"name": "wells.xlsx", "status": "success", "rows_imported": 12}},
        fake_bucket,
    )

    assert chemistry_drive.manifest_databases(fake_bucket) == [
        "ocotillo-prod-copy",
        "ocotillo-staging",
    ]

    overview = chemistry_drive.manifest_overview(fake_bucket)
    assert overview.files["F1"]["name"] == "wells.xlsx"
    assert set(overview.files["F1"]["databases"]) == {
        "ocotillo-prod-copy",
        "ocotillo-staging",
    }
    # F2 only ever ingested locally, so staging is absent rather than blank.
    assert set(overview.files["F2"]["databases"]) == {"ocotillo-prod-copy"}


def test_manifest_overview_separates_corrupt_manifest(monkeypatch, fake_bucket):
    """A corrupt manifest must not read as 'not ingested there'."""
    monkeypatch.delenv("CHEMISTRY_INGEST_MANIFEST_PATH", raising=False)
    monkeypatch.setenv("POSTGRES_DB", "ocotillo-staging")
    save_manifest({"F1": {"name": "wells.xlsx", "status": "success"}}, fake_bucket)
    fake_bucket.store["chemistry-ingest/manifest.broken.json"] = "{not json"

    overview = chemistry_drive.manifest_overview(fake_bucket)
    assert overview.databases == ["ocotillo-staging"]
    assert overview.unreadable == ["broken"]
    assert set(overview.files["F1"]["databases"]) == {"ocotillo-staging"}


def test_missing_folder_raises(monkeypatch):
    monkeypatch.delenv("CHEMISTRY_DRIVE_FOLDER_ID", raising=False)
    with pytest.raises(ChemistryDriveConfigError):
        sync_and_ingest(folder_id=None)


@pytest.mark.parametrize("bucket_name", ["", "   "])
def test_missing_manifest_bucket_raises(monkeypatch, bucket_name):
    """An unset GCS_BUCKET_NAME must fail as a config error, not an IndexError."""
    monkeypatch.setenv("GCS_BUCKET_NAME", bucket_name)
    with pytest.raises(ChemistryDriveConfigError, match="GCS_BUCKET_NAME"):
        sync_and_ingest(folder_id="folder")


def test_dry_run_missing_manifest_bucket_raises(monkeypatch):
    """The dry run reads the manifest too, so it fails the same clean way."""
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    with pytest.raises(ChemistryDriveConfigError, match="GCS_BUCKET_NAME"):
        sync_and_ingest(folder_id="folder", dry_run=True)


# ------------------------- folder access tests -------------------------------


class _FakeHttpError(Exception):
    """Stand-in for googleapiclient.errors.HttpError with a status code."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = SimpleNamespace(status=status)


class _FakeFilesApi:
    def __init__(self, error=None):
        self._error = error
        self.get_called_with = None

    def get(self, **kwargs):
        self.get_called_with = kwargs

        def _execute():
            if self._error:
                raise self._error
            return {"id": kwargs.get("fileId")}

        return SimpleNamespace(execute=_execute)


class _FakeDriveService:
    def __init__(self, error=None):
        self.files_api = _FakeFilesApi(error)

    def files(self):
        return self.files_api


@pytest.fixture()
def _fake_http_error(monkeypatch):
    """Make the service module treat _FakeHttpError as googleapiclient's."""
    module = types.ModuleType("googleapiclient.errors")
    module.HttpError = _FakeHttpError
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", module)


@pytest.mark.parametrize("status", [403, 404])
def test_unshared_folder_raises_config_error(_fake_http_error, status):
    """Drive returns notFound for an unshared folder; that must not look empty."""
    service = _FakeDriveService(error=_FakeHttpError(status))
    with pytest.raises(ChemistryDriveConfigError, match="not accessible"):
        assert_folder_accessible("folder", service=service)


def test_accessible_folder_passes(_fake_http_error):
    service = _FakeDriveService()
    assert_folder_accessible("folder", service=service) is None
    assert service.files_api.get_called_with["fileId"] == "folder"


def test_unexpected_http_error_is_not_swallowed(_fake_http_error):
    """A 500 is a transient Drive fault, not a misconfiguration -- let it bubble."""
    service = _FakeDriveService(error=_FakeHttpError(500))
    with pytest.raises(_FakeHttpError):
        assert_folder_accessible("folder", service=service)


# ------------------------- sync tests ----------------------------------------


def test_sync_ingests_new_file_and_records_manifest(
    monkeypatch, fake_bucket, water_well_thing, _cleanup_chemistry
):
    files = [
        {"id": "F1", "name": "batch1.xlsx", "md5Checksum": "abc", "modifiedTime": "t0"}
    ]
    _stub_drive(monkeypatch, files, {"F1": _workbook_bytes()})

    result = sync_and_ingest(folder_id="folder", bucket=fake_bucket)

    assert result.exit_code == 0
    assert len(result.ingested) == 1
    assert result.ingested[0]["rows_imported"] == 1
    manifest = load_manifest(fake_bucket)
    assert manifest["F1"]["status"] == "success"
    assert manifest["F1"]["md5"] == "abc"


def test_sync_skips_already_ingested_file(
    monkeypatch, fake_bucket, water_well_thing, _cleanup_chemistry
):
    files = [
        {"id": "F1", "name": "batch1.xlsx", "md5Checksum": "abc", "modifiedTime": "t0"}
    ]
    _stub_drive(monkeypatch, files, {"F1": _workbook_bytes()})

    first = sync_and_ingest(folder_id="folder", bucket=fake_bucket)
    assert len(first.ingested) == 1

    second = sync_and_ingest(folder_id="folder", bucket=fake_bucket)
    assert second.ingested == []
    assert second.skipped == ["batch1.xlsx"]


def test_dry_run_does_not_download_or_write_manifest(
    monkeypatch, fake_bucket, water_well_thing, _cleanup_chemistry
):
    files = [
        {"id": "F1", "name": "batch1.xlsx", "md5Checksum": "abc", "modifiedTime": "t0"}
    ]
    monkeypatch.setattr(
        chemistry_drive, "list_drive_xlsx", lambda folder_id, service=None: files
    )

    def _boom(file_id, service=None):
        raise AssertionError("download must not be called during a dry run")

    monkeypatch.setattr(chemistry_drive, "download_drive_file", _boom)

    result = sync_and_ingest(folder_id="folder", bucket=fake_bucket, dry_run=True)

    assert result.dry_run is True
    assert result.new_files == ["batch1.xlsx"]
    assert result.ingested == []
    assert load_manifest(fake_bucket) == {}


def test_sync_marks_failed_when_ingestion_aborts(
    monkeypatch, fake_bucket, water_well_thing, _cleanup_chemistry
):
    # A workbook whose SamplePointID has no matching Thing aborts (validation
    # error) -> the file is recorded as failed.
    _stub_drive(
        monkeypatch,
        [{"id": "F1", "name": "bad.xlsx", "md5Checksum": "abc", "modifiedTime": "t0"}],
        {"F1": _workbook_bytes(pointid="NO-SUCH-WELL")},
    )
    result = sync_and_ingest(folder_id="folder", bucket=fake_bucket)

    assert result.exit_code == 1
    assert len(result.failed) == 1
    assert result.failed[0]["name"] == "bad.xlsx"
    assert load_manifest(fake_bucket)["F1"]["status"] == "failed"


# ============= EOF =============================================
