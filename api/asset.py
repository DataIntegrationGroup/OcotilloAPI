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
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db_session
from db.asset import Asset

router = APIRouter(prefix="/asset", tags=["asset"])


@router.get("/{asset_id}")
async def get_asset(asset_id: int, database_session: Session = Depends(get_db_session)):
    """
    Retrieve an asset by its ID.
    """
    sql = select(Asset).where(Asset.id == asset_id)
    return database_session.scalars(sql).one_or_none()


@router.post("/", status_code=201)
async def add_asset(
    file: UploadFile, database_session: Session = Depends(get_db_session)
):
    """
    Add a new asset.
    """
    asset = Asset()
    asset.name = file.filename
    asset.file_type = file.content_type

    content = file.file.read()
    asset.content = content
    if file.content_type.startswith("image/"):
        asset.photo = content

    database_session.add(asset)
    database_session.commit()
    return asset


# ============= EOF =============================================
