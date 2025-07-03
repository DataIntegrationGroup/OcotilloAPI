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

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db_session
from db.asset import Asset

router = APIRouter(prefix="/asset", tags=["asset"])
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")


def get_storage_bucket():
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket


@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    database_session: Session = Depends(get_db_session),
    bucket=Depends(
        get_storage_bucket
    ),  # Assuming get_storage_bucket is defined elsewhere
):
    """
    Retrieve an asset by its ID.
    """
    sql = select(Asset).where(Asset.id == asset_id)
    asset = database_session.scalars(sql).one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    blob = bucket.blob(asset.storage_path)
    asset.url = blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET")
    return asset


@router.post("/", status_code=201)
async def add_asset(
    file: UploadFile = File(...),
    database_session: Session = Depends(get_db_session),
    bucket=Depends(get_storage_bucket),
):
    file_id = str(uuid4())
    blob_name = f"uploads/{file_id}_{file.filename}"
    blob = bucket.blob(blob_name)

    blob.upload_from_file(file.file, content_type=file.content_type)

    asset = Asset(
        filename=file.filename,
        storage_service="gcs",
        storage_path=blob_name,
        mime_type=file.content_type,
        size=file.size,
    )
    database_session.add(asset)
    database_session.commit()
    database_session.refresh(asset)

    return {
        "id": asset.id,
        "filename": asset.filename,
        "url": f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}",
    }


# ============= EOF =============================================
