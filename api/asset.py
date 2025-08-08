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
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import Thing
from db.asset import Asset, AssetThingAssociation
from schemas.asset import AssetResponse, CreateAsset, UpdateAsset
from services.crud_helper import model_patcher

router = APIRouter(prefix="/asset", tags=["asset"])
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")


from google.cloud import storage


def get_storage_bucket() -> storage.Bucket:
    client = storage.Client.from_service_account_json(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    bucket = client.bucket(GCS_BUCKET_NAME)
    return bucket


@router.get("")
async def list_assets(
    session: session_dependency,
    # bucket=Depends(get_storage_bucket),
    thing_id: int = None,
) -> CustomPage[AssetResponse]:
    """
    List all assets or assets associated with a specific thing.
    """
    sql = select(Asset)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )

    # assets = session.scalars(sql).all()
    # if not assets:
    #     return []

    def transformer(assets: List[Asset]) -> AssetResponse:
        # blob = bucket.blob(asset.storage_path)
        # asset.url = blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET")
        # return [AssetResponse.model_validate(asset) for asset in assets]
        for a in assets:
            a.url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{a.storage_path}"
        return assets

    return paginate(query=sql, conn=session, transformer=transformer)


@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    session: session_dependency,
    bucket=Depends(
        get_storage_bucket
    ),  # Assuming get_storage_bucket is defined elsewhere
    thing_id: int = None,
) -> AssetResponse:
    """
    Retrieve an asset by its ID.
    """
    sql = select(Asset)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )
    else:
        sql = sql.where(Asset.id == asset_id)

    asset = session.scalars(sql).one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    blob = bucket.blob(asset.storage_path)
    asset.url = blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET")
    return asset


@router.post("/upload", status_code=HTTP_201_CREATED)
async def upload_asset(
    bucket=Depends(get_storage_bucket), file: UploadFile = File(...)
):
    file_id = str(uuid4())
    blob_name = f"uploads/{file_id}_{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    return {
        "url": blob.generate_signed_url(expiration=timedelta(minutes=10), method="GET"),
        "storage_path": blob_name,
    }


@router.post("", status_code=HTTP_201_CREATED)
async def add_asset(
    session: session_dependency, asset_data: CreateAsset
) -> AssetResponse:

    data = asset_data.model_dump()
    thing_id = data.pop("thing_id", None)
    url = data.pop("url", "")

    data["storage_service"] = "gcs"
    asset = Asset(**data)

    if thing_id:
        assoc = AssetThingAssociation()
        thing = session.get(Thing, thing_id)
        assoc.thing = thing
        assoc.asset = asset
        session.add(assoc)

    session.add(asset)
    session.commit()
    session.refresh(asset)
    asset.url = url
    return asset


@router.patch("/{asset_id}")
async def update_asset(
    asset_id: int, session: session_dependency, asset_data: UpdateAsset
):
    """
    Update an existing asset.
    """
    return model_patcher(session, Asset, asset_id, asset_data)


# ============= EOF =============================================
