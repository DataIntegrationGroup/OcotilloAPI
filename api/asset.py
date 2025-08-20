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

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from starlette.status import HTTP_201_CREATED, HTTP_409_CONFLICT

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
from services.query_helper import simple_get_by_id
from services.gcs_helper import (
    get_storage_bucket,
    gcs_upload,
    check_asset_exists,
    add_signed_url,
)
from services.exceptions_helper import PydanticStyleException

router = APIRouter(
    prefix="/asset", tags=["asset"], dependencies=[Depends(viewer_function)]
)


def database_error_handler(payload: CreateAsset, error: ProgrammingError) -> None:
    """
    Handle errors raised by the database when adding or updating a sample.
    """

    error_message = error.orig.args[0]["M"]
    print(error_message)

    if (
        error_message
        == 'null value in column "thing_id" of relation "asset_thing_association" violates not-null constraint'
    ):
        """
        Developer's notes

        this error occurs because the thing_id is set by the Thing record that
        is retrieved, so if there is no Thing with thing_id it tries to set
        thing_id to None in the AssetThingAssociation table
        """
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} not found.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }

    raise PydanticStyleException(status_code=HTTP_409_CONFLICT, detail=[detail])


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

    try:
        data = asset_data.model_dump()
        print(data)
        thing_id = data.pop("thing_id", None)
        print(thing_id)
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
    except ProgrammingError as e:
        database_error_handler(asset_data, e)


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

    def transformer(a):
        if thing_id is not None:
            add_signed_url(a, get_storage_bucket())
        return a

    return paginate(query=sql, conn=session, transformer=transformer)


@router.get("/{asset_id}")
async def get_asset(
    asset_id: int,
    session: session_dependency,
    bucket=Depends(get_storage_bucket),
) -> AssetResponse:
    """
    Retrieve an asset by its ID.
    """
    return simple_get_by_id(session, Asset, asset_id)


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
