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

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    viewer_function,
    admin_dependency,
    admin_function,
    editor_dependency,
)
from db import Thing
from db.asset import Asset, AssetThingAssociation
from schemas.asset import AssetResponse, CreateAsset, UpdateAsset
from services.audit_helper import audit_add
from services.crud_helper import model_patcher
from services.gcs_helper import (
    get_storage_bucket,
    gcs_upload,
    check_asset_exists,
    add_signed_url,
)

router = APIRouter(
    prefix="/asset", tags=["asset"], dependencies=[Depends(viewer_function)]
)


# ======= Create =========
@router.post(
    "/upload", status_code=HTTP_201_CREATED, dependencies=[Depends(admin_function)]
)
async def upload_asset(
    bucket=Depends(get_storage_bucket), file: UploadFile = File(...)
):
    uri, blob_name = gcs_upload(file, bucket)
    return {
        "uri": uri,
        "storage_path": blob_name,
    }


@router.post("", status_code=HTTP_201_CREATED)
async def add_asset(
    user: admin_dependency, session: session_dependency, asset_data: CreateAsset
) -> AssetResponse:

    data = asset_data.model_dump()
    thing_id = data.pop("thing_id", None)
    storage_path = data["storage_path"]

    # check to see if an asset entry already exists for
    # this storage path and thing_id
    existing_asset = check_asset_exists(session, storage_path, thing_id=thing_id)
    if existing_asset:
        # If an asset already exists, return it
        return existing_asset

    data["storage_service"] = "gcs"
    asset = Asset(**data)
    audit_add(user, asset)

    if thing_id:
        assoc = AssetThingAssociation()
        audit_add(user, assoc)
        thing = session.get(Thing, thing_id)
        assoc.thing = thing
        assoc.asset = asset
        session.add(assoc)

    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


# ======= Read =========
@router.get("")
async def list_assets(
    session: session_dependency, thing_id: int = None
) -> CustomPage[AssetResponse]:
    """
    List all assets or assets associated with a specific thing.
    """
    sql = select(Asset)
    if thing_id:
        sql = sql.join(AssetThingAssociation).where(
            AssetThingAssociation.thing_id == thing_id
        )

    def transformer(records: list[Asset]):
        if thing_id is not None:
            bucket = get_storage_bucket()
            records = [add_signed_url(ai, bucket) for ai in records]

        return records

    return paginate(query=sql, conn=session, transformer=transformer)


@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    session: session_dependency,
    thing_id: int = None,
    bucket=Depends(get_storage_bucket),
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

    add_signed_url(asset, bucket)
    return asset


# ======= Update =========
@router.patch("/{asset_id}")
async def update_asset(
    asset_id: int,
    session: session_dependency,
    asset_data: UpdateAsset,
    user: editor_dependency,
):
    """
    Update an existing asset.
    """
    return model_patcher(session, Asset, asset_id, asset_data, user=user)


# ============= EOF =============================================
