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
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, DeclarativeBase
from starlette.status import HTTP_404_NOT_FOUND

from services.query_helper import simple_get_by_id


def model_patcher(
    session: Session,
    model: DeclarativeBase,
    item_id: int,
    payload: BaseModel,
    user: dict = None,
):
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    item = simple_get_by_id(session, model, item_id)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    if user:
        item.updated_by_id = user["sub"]
        item.updated_by_name = user["name"]

    session.commit()
    session.refresh(item)
    return item


# ============= EOF =============================================
