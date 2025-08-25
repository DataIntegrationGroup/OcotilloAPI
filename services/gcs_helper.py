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
import json
import os
import datetime
from hashlib import md5
from fastapi import UploadFile
from google.oauth2 import service_account
from sqlalchemy import select
from core.settings import settings
from db import Asset, AssetThingAssociation

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
GCS_BUCKET_BASE_URL = f"https://storage.cloud.google.com/{GCS_BUCKET_NAME}/uploads"

from google.cloud import storage


def get_storage_bucket() -> storage.Bucket:

    if settings.mode == "production":
        key_json = os.environ.get("GCS_SERVICE_ACCOUNT_KEY")
        # Load service account credentials
        creds = service_account.Credentials.from_service_account_info(
            json.loads(key_json)
        )

        # Create storage client
        client = storage.Client(credentials=creds)
    else:
        client = storage.Client.from_service_account_json(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )

    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket


def gcs_upload(file: UploadFile, bucket: storage.Bucket = None):
    if bucket is None:
        bucket = get_storage_bucket()

    # make file id from hash of file contents
    file.file.seek(0)
    file_id = md5(file.file.read()).hexdigest()

    head, extension = os.path.splitext(file.filename)

    blob_name = f"uploads/{head}_{file_id}{extension}"
    eblob = bucket.get_blob(blob_name)
    if eblob:
        print("blob exists")
        return (
            f"{GCS_BUCKET_BASE_URL}/{blob_name}",
            blob_name,
        )

    blob = bucket.blob(blob_name)

    file.file.seek(0)
    blob.upload_from_file(file.file, content_type=file.content_type)
    url = f"{GCS_BUCKET_BASE_URL}/{blob_name}"
    return url, blob_name


def gcs_remove(uri: str, bucket: storage.Bucket):
    blob = bucket.blob(uri)
    blob.delete()


def add_signed_url(asset: Asset, bucket: storage.Bucket):
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
