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
import os
from hashlib import md5

from fastapi import UploadFile
from sqlalchemy import select

from core.settings import settings
from db import Asset, AssetThingAssociation

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
GCS_BUCKET_BASE_URL = f"https://storage.cloud.google.com/{GCS_BUCKET_NAME}/uploads"


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
        # Use application default credentials (from ~/.config/gcloud/application_default_credentials.json)
        # This will automatically use GOOGLE_APPLICATION_CREDENTIALS if set, or the default location
        client = storage.Client()
    return client


def get_storage_bucket(client=None, bucket: str = None):
    if client is None:
        client = get_storage_client()

    if bucket is None:
        bucket = GCS_BUCKET_NAME

    return client.bucket(bucket)


def make_blob_name_and_uri(file):
    head, extension = os.path.splitext(file.filename)
    file_id = md5(file.file.read()).hexdigest()

    blob_name = f"{head}_{file_id}{extension}"
    uri = f"{GCS_BUCKET_BASE_URL}/{blob_name}"
    return blob_name, uri


def gcs_upload(file: UploadFile, bucket=None):
    if bucket is None:
        bucket = get_storage_bucket()

    # make file id from hash of file contents
    file.file.seek(0)

    blob_name, uri = make_blob_name_and_uri(file)
    eblob = bucket.get_blob(blob_name)

    if not eblob:
        blob = bucket.blob(blob_name)
        file.file.seek(0)
        blob.upload_from_file(file.file, content_type=file.content_type)
    return uri, blob_name


def gcs_remove(uri: str, bucket):
    blob = bucket.blob(uri)
    blob.delete()


def add_signed_url(asset: Asset, bucket):
    asset.signed_url = bucket.blob(asset.storage_path).generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="GET",
    )
    return asset


def check_asset_exists(session, blob_name, thing_id=None):
    sql = select(Asset).where(Asset.storage_path == blob_name)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )
    return session.scalars(sql).one_or_none()


# ============= EOF =============================================
