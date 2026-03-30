# ===============================================================================
# Copyright 2025 ross
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
import base64
import datetime
import json
import logging
import os
import time
from functools import lru_cache
from hashlib import md5

from fastapi import UploadFile
from sqlalchemy import select

from core.settings import settings
from db import Asset, AssetThingAssociation
from services.env import get_bool_env

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
GCS_BUCKET_BASE_URL = f"https://storage.cloud.google.com/{GCS_BUCKET_NAME}/uploads"
GCS_LOOKUP_TIMEOUT_SECS = float(os.environ.get("GCS_LOOKUP_TIMEOUT_SECS", "15"))
GCS_UPLOAD_TIMEOUT_SECS = float(os.environ.get("GCS_UPLOAD_TIMEOUT_SECS", "120"))
logger = logging.getLogger(__name__)
HASH_CHUNK_SIZE = 1024 * 1024


def is_debug_timing_enabled() -> bool:
    return bool(get_bool_env("API_DEBUG_TIMING", False))


@lru_cache(maxsize=1)
def get_storage_client():
    from google.cloud import storage
    from google.oauth2 import service_account

    if settings.mode == "production":
        key_base64 = os.environ.get("GCS_SERVICE_ACCOUNT_KEY")
        decoded = base64.b64decode(key_base64).decode("utf-8")

        # Load service account credentials
        creds = service_account.Credentials.from_service_account_info(
            json.loads(decoded)
        )

        # Create storage client
        client = storage.Client(credentials=creds)
    else:
        # Use application default credentials from gcloud or
        # GOOGLE_APPLICATION_CREDENTIALS when present.
        client = storage.Client()
    return client


@lru_cache(maxsize=8)
def _get_cached_bucket(bucket_name: str):
    return get_storage_client().bucket(bucket_name)


def get_storage_bucket(client=None, bucket: str = None):
    bucket_name = bucket or GCS_BUCKET_NAME
    if client is not None:
        return client.bucket(bucket_name)
    return _get_cached_bucket(bucket_name)


def _log_stage(stage: str, started_at: float, **extra):
    if not is_debug_timing_enabled():
        return
    record_extra = {
        "event": "gcs_stage_timing",
        "stage": stage,
        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    if "filename" in extra:
        record_extra["upload_filename"] = extra.pop("filename")
    logger.info(
        "gcs stage timing",
        extra={**record_extra, **extra},
    )


def _hash_file(file_obj) -> str:
    hasher = md5()
    while True:
        chunk = file_obj.read(HASH_CHUNK_SIZE)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()


def make_blob_name_and_uri(file):
    started_at = time.perf_counter()
    head, extension = os.path.splitext(file.filename)
    file.file.seek(0)
    file_id = _hash_file(file.file)
    file.file.seek(0)

    blob_name = f"{head}_{file_id}{extension}"
    uri = f"{GCS_BUCKET_BASE_URL}/{blob_name}"
    _log_stage(
        "hash_file",
        started_at,
        filename=file.filename,
        blob_name=blob_name,
    )
    return blob_name, uri


def gcs_upload(file: UploadFile, bucket=None):
    upload_started_at = time.perf_counter()
    if bucket is None:
        bucket_started_at = time.perf_counter()
        bucket = get_storage_bucket()
        _log_stage("resolve_bucket", bucket_started_at, filename=file.filename)

    # make file id from hash of file contents
    file.file.seek(0)

    blob_name, uri = make_blob_name_and_uri(file)
    lookup_started_at = time.perf_counter()
    eblob = bucket.get_blob(blob_name, timeout=GCS_LOOKUP_TIMEOUT_SECS)
    _log_stage(
        "lookup_blob",
        lookup_started_at,
        filename=file.filename,
        blob_name=blob_name,
        blob_exists=eblob is not None,
    )

    if not eblob:
        blob = bucket.blob(blob_name)
        file.file.seek(0)
        upload_blob_started_at = time.perf_counter()
        blob.upload_from_file(
            file.file,
            content_type=file.content_type,
            timeout=GCS_UPLOAD_TIMEOUT_SECS,
        )
        _log_stage(
            "upload_blob",
            upload_blob_started_at,
            filename=file.filename,
            blob_name=blob_name,
        )
    _log_stage(
        "upload_request_total",
        upload_started_at,
        filename=file.filename,
        blob_name=blob_name,
    )
    return uri, blob_name


def gcs_remove(uri: str, bucket):
    blob = bucket.blob(uri)
    blob.delete()


def add_signed_url(asset: Asset, bucket):
    started_at = time.perf_counter()
    try:
        asset.signed_url = bucket.blob(asset.storage_path).generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
        )
        _log_stage(
            "generate_signed_url",
            started_at,
            asset_id=getattr(asset, "id", None),
            storage_path=getattr(asset, "storage_path", None),
        )
    except Exception:
        logger.warning(
            "Failed to generate signed URL for asset_id=%s storage_path=%s",
            getattr(asset, "id", None),
            getattr(asset, "storage_path", None),
            exc_info=True,
        )
        asset.signed_url = None
    return asset


def check_asset_exists(session, blob_name, thing_id=None):
    sql = select(Asset).where(Asset.storage_path == blob_name)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )
    return session.scalars(sql).one_or_none()


# ============= EOF =============================================
