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
import os
from datetime import timedelta
from uuid import uuid4

from fastapi import File, UploadFile

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")


from google.cloud import storage


def get_storage_bucket() -> storage.Bucket:
    client = storage.Client.from_service_account_json(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket


def gcs_upload(file: UploadFile, bucket: storage.Bucket = None):
    if bucket is None:
        bucket = get_storage_bucket()

    file_id = str(uuid4())
    head, extension = os.path.splitext(file.filename)

    blob_name = f"uploads/{head}_{file_id}{extension}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    signed_url = blob.generate_signed_url(
        expiration=timedelta(minutes=10), method="GET"
    )

    return signed_url, blob_name


def set_asset_url(asset, bucket=None):
    if bucket is None:
        bucket = get_storage_bucket()
    blob = bucket.blob(asset.storage_path)
    asset.url = blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET")


# ============= EOF =============================================
