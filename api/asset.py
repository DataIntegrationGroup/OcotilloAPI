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
from starlette.status import HTTP_201_CREATED, HTTP_409_CONFLICT, HTTP_204_NO_CONTENT

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
from services.crud_helper import model_patcher, model_deleter
from services.query_helper import simple_get_by_id
from services.gcs_helper import (
    get_storage_bucket,
    gcs_upload,
    gcs_remove,
    check_asset_exists,
    add_signed_url,
)
from services.exceptions_helper import PydanticStyleException

router = APIRouter(
    prefix="/asset", tags=["asset"], dependencies=[Depends(viewer_function)]
)


def database_error_handler(payload: CreateAsset, error: ProgrammingError) -> None:
    """
    Handle errors raised by the database when adding or updating a asset.
    """

    error_message = error.orig.args[0]["M"]

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


# POST =========================================================================
@router.post(
    "/upload",
    status_code=HTTP_201_CREATED,
    dependencies=[Depends(admin_function)],
)
async def upload_asset(
    bucket=Depends(get_storage_bucket), file: UploadFile = File(...)
) -> dict:
    uri, blob_name = gcs_upload(file, bucket)
    return {
        "uri": uri,
        "storage_path": blob_name,
    }


@router.post("", status_code=HTTP_201_CREATED)
async def add_asset(
    user: admin_dependency,
    session: session_dependency,
    asset_data: CreateAsset,
) -> AssetResponse:

    try:
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
    except ProgrammingError as e:
        database_error_handler(asset_data, e)


# GET ==========================================================================

"""
Developer's notes

Do not generate signed urls when listing ALL assets. There is a reason to
generate signed urls when listing assets for a given `thing_id` because this
is used by the front end to display a gallery of images all at once. This is
the only case in which signed urls should be generated for a list of assets. A
signed url is always generated when retrieving assets individually
"""


@router.get("")
async def list_assets(
    session: session_dependency,
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
    bucket=Depends(get_storage_bucket),
) -> AssetResponse:
    """
    Retrieve an asset by its ID.
    """
    asset = simple_get_by_id(session, Asset, asset_id)

    add_signed_url(asset, bucket)
    return asset


# PATCH ========================================================================
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


# DELETE =======================================================================


@router.delete("/{asset_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int, session: session_dependency, user: admin_dependency
):

    # TODO: Interesting issue here.  we don't have a way of tracking who deleted a record
    return model_deleter(session, Asset, asset_id)


@router.delete(
    "/{asset_id}/remove",
    status_code=HTTP_204_NO_CONTENT,
    dependencies=[Depends(admin_function)],
)
async def remove_asset(
    asset_id: int,
    session: session_dependency,
    bucket=Depends(get_storage_bucket),
):
    asset = simple_get_by_id(session, Asset, asset_id)
    gcs_remove(asset.uri, bucket)


# ============= EOF =============================================
