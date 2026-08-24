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
Ingest LIMS chemistry workbooks from a Google Drive folder, on demand.

This is explicitly engineer-triggered: it runs once per invocation and does no
polling or scheduling. New/changed ``.xlsx`` files under
``CHEMISTRY_DRIVE_FOLDER_ID`` are downloaded and handed to
:func:`services.chemistry_lims.bulk_upload_chemistry`. A manifest of
already-ingested files is kept as a JSON object in the GCS bucket. By default
the manifest path is scoped per target database (``chemistry-ingest/manifest.
<postgres_db>.json``) so pointing ``.env`` at a different database -- local
copy, staging, production -- never skips a file on the strength of an ingest
into a different database.

Configuration (environment variables):
* ``CHEMISTRY_DRIVE_FOLDER_ID`` - Drive folder id to scan (shared-drive or
  My-Drive folder shared with the service account).
* ``CHEMISTRY_INGEST_MANIFEST_PATH`` - GCS object key for the manifest.
  Overrides the per-database default below.
* ``GCS_BUCKET_NAME`` - bucket that holds the manifest (shared with gcs_helper).

Authentication mirrors ``services.gcs_helper``: in production the base64
service-account key in ``GCS_SERVICE_ACCOUNT_KEY`` is used (with a Drive scope);
otherwise application-default credentials are used. The service account must be
granted at least read access to the target Drive folder.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from core.settings import settings
from services.chemistry_lims import bulk_upload_chemistry
from services.gcs_helper import get_storage_bucket

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MANIFEST_PREFIX = "chemistry-ingest/"


class ChemistryDriveConfigError(Exception):
    """The ingest is not configured (missing folder id or manifest bucket)."""


# --- Google Drive access -------------------------------------------------------


def _drive_credentials():
    from google.oauth2 import service_account

    if settings.mode == "production":
        key_base64 = os.environ.get("GCS_SERVICE_ACCOUNT_KEY")
        if not key_base64:
            raise ChemistryDriveConfigError(
                "GCS_SERVICE_ACCOUNT_KEY is required for Drive access in production."
            )
        decoded = base64.b64decode(key_base64).decode("utf-8")
        return service_account.Credentials.from_service_account_info(
            json.loads(decoded), scopes=DRIVE_SCOPES
        )

    import google.auth

    creds, _ = google.auth.default(scopes=DRIVE_SCOPES)
    return creds


@lru_cache(maxsize=1)
def get_drive_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_drive_credentials(), cache_discovery=False)


def assert_folder_accessible(folder_id: str, service=None) -> None:
    """Fail loudly when the folder is missing or not shared with our identity.

    Drive answers ``notFound`` for a folder the caller cannot see, so an
    unshared folder is indistinguishable from an empty one on a plain list
    call. Without this check a missing share reads as "nothing new to
    ingest" and real lab batches sit unprocessed with a zero exit code.
    """
    from googleapiclient.errors import HttpError

    service = service or get_drive_service()
    try:
        service.files().get(
            fileId=folder_id, fields="id", supportsAllDrives=True
        ).execute()
    except HttpError as exc:
        if exc.resp.status in (403, 404):
            raise ChemistryDriveConfigError(
                f"Drive folder {folder_id!r} is not accessible. Check the folder id, "
                "and that the folder is shared with the account running the ingest."
            ) from exc
        raise


def list_drive_xlsx(folder_id: str, service=None) -> list[dict]:
    """List non-trashed ``.xlsx`` files directly under ``folder_id``."""
    service = service or get_drive_service()
    assert_folder_accessible(folder_id, service=service)
    query = (
        f"'{folder_id}' in parents "
        "and trashed = false "
        f"and mimeType = '{XLSX_MIME}'"
    )
    files: list[dict] = []
    page_token = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                corpora="allDrives",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="nextPageToken, files(id, name, md5Checksum, modifiedTime, size)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return files


def download_drive_file(file_id: str, service=None) -> bytes:
    """Download a Drive file's bytes."""
    from googleapiclient.http import MediaIoBaseDownload

    service = service or get_drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return buffer.getvalue()


# --- manifest (GCS JSON object) ------------------------------------------------


def _manifest_db_suffix() -> str:
    """Slug the target database name for use in a manifest path.

    Scoping by ``POSTGRES_DB`` (rather than a separate "which environment am
    I" variable) means the manifest can never disagree with the database
    ``.env`` is actually pointed at -- there is nothing to keep in sync.
    """
    db_name = os.environ.get("POSTGRES_DB", "").strip().lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", db_name).strip("-")
    return slug or "unknown"


def _manifest_path() -> str:
    override = os.environ.get("CHEMISTRY_INGEST_MANIFEST_PATH")
    if override:
        return override
    return f"{MANIFEST_PREFIX}manifest.{_manifest_db_suffix()}.json"


def _manifest_bucket():
    """Resolve the manifest bucket, failing cleanly when it is unconfigured.

    ``get_storage_bucket`` raises an opaque ``IndexError`` from deep inside the
    storage client when the bucket name is empty, so check it here first.
    """
    if not (os.environ.get("GCS_BUCKET_NAME") or "").strip():
        raise ChemistryDriveConfigError(
            "No manifest bucket configured. Set GCS_BUCKET_NAME to the bucket "
            "holding the chemistry ingest manifest."
        )
    return get_storage_bucket()


def load_manifest(bucket=None) -> dict[str, dict]:
    bucket = bucket or _manifest_bucket()
    blob = bucket.blob(_manifest_path())
    if not blob.exists():
        return {}
    try:
        return json.loads(blob.download_as_text())
    except (ValueError, json.JSONDecodeError):
        logger.warning("Chemistry ingest manifest is corrupt; starting fresh.")
        return {}


def save_manifest(manifest: dict[str, dict], bucket=None) -> None:
    bucket = bucket or _manifest_bucket()
    blob = bucket.blob(_manifest_path())
    blob.upload_from_string(
        json.dumps(manifest, indent=2, sort_keys=True),
        content_type="application/json",
    )


# --- orchestration -------------------------------------------------------------


@dataclass
class DriveSyncResult:
    folder_id: str
    files_seen: int = 0
    new_files: list[str] = field(default_factory=list)
    ingested: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    dry_run: bool = False

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def to_payload(self) -> dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "dry_run": self.dry_run,
            "summary": {
                "files_seen": self.files_seen,
                "new_files": len(self.new_files),
                "ingested": len(self.ingested),
                "skipped": len(self.skipped),
                "failed": len(self.failed),
            },
            "new_files": self.new_files,
            "ingested": self.ingested,
            "skipped": self.skipped,
            "failed": self.failed,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sync_and_ingest(
    folder_id: str | None = None,
    *,
    dry_run: bool = False,
    bucket=None,
    drive_service=None,
) -> DriveSyncResult:
    """Scan the Drive folder and ingest any new or changed workbooks.

    A file is considered already ingested when the manifest holds a
    ``success`` entry whose ``md5`` matches the current Drive checksum. Failed
    or changed files are retried on the next run.
    """
    folder_id = folder_id or os.environ.get("CHEMISTRY_DRIVE_FOLDER_ID")
    if not folder_id:
        raise ChemistryDriveConfigError(
            "No Drive folder configured. Set CHEMISTRY_DRIVE_FOLDER_ID or pass --folder-id."
        )

    bucket = bucket or _manifest_bucket()
    manifest = load_manifest(bucket)
    files = list_drive_xlsx(folder_id, service=drive_service)

    result = DriveSyncResult(
        folder_id=folder_id, files_seen=len(files), dry_run=dry_run
    )

    for meta in files:
        file_id = meta["id"]
        name = meta.get("name", file_id)
        md5 = meta.get("md5Checksum")

        entry = manifest.get(file_id)
        already_ingested = (
            entry is not None
            and entry.get("status") == "success"
            and entry.get("md5") == md5
        )
        if already_ingested:
            result.skipped.append(name)
            continue

        result.new_files.append(name)
        if dry_run:
            continue

        logger.info("Ingesting chemistry workbook from Drive: %s (%s)", name, file_id)
        try:
            data = download_drive_file(file_id, service=drive_service)
            upload = bulk_upload_chemistry(data)
        except Exception as exc:  # network / parse / DB failure for this file
            logger.exception("Failed to ingest Drive file %s (%s)", name, file_id)
            record = {
                "name": name,
                "file_id": file_id,
                "status": "failed",
                "error": str(exc),
            }
            manifest[file_id] = {
                "name": name,
                "md5": md5,
                "modified_time": meta.get("modifiedTime"),
                "status": "failed",
                "error": str(exc),
                "ingested_at": _now_iso(),
            }
            save_manifest(manifest, bucket)
            result.failed.append(record)
            continue

        summary = upload.payload.get("summary", {})
        status = "success" if upload.exit_code == 0 else "failed"
        manifest[file_id] = {
            "name": name,
            "md5": md5,
            "modified_time": meta.get("modifiedTime"),
            "status": status,
            "rows_imported": summary.get("total_rows_imported", 0),
            "validation_errors_or_warnings": summary.get(
                "validation_errors_or_warnings", 0
            ),
            "ingested_at": _now_iso(),
        }
        # Persist after every file so an interrupted run keeps its progress.
        save_manifest(manifest, bucket)

        record = {
            "name": name,
            "file_id": file_id,
            "status": status,
            "rows_imported": summary.get("total_rows_imported", 0),
            "payload": upload.payload,
        }
        if status == "success":
            result.ingested.append(record)
        else:
            result.failed.append(record)

    return result


# ============= EOF =============================================
