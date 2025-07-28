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

from fastapi import Depends, APIRouter, Query
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder
from db.engine import get_db_session
from db.group import Group, GroupThingAssociation
from schemas_v2.group import UpdateGroup
from schemas_v2.location import CreateGroup, CreateGroupThing
from schemas_v2.thing import GroupResponse
from services.crud_helper import model_patcher
from services.query_helper import (
    simple_get_by_id,
    paginated_all_getter,
)

router = APIRouter(prefix="/group", tags=["group"])


@router.post("", summary="Create a new group", status_code=status.HTTP_201_CREATED)
def create_group(group_data: CreateGroup, session: session_dependency):
    """
    Create a new group in the database.
    """
    return adder(session, Group, group_data)


@router.post(
    "/association",
    summary="Create a new group-thing association",
    status_code=status.HTTP_201_CREATED,
)
def create_group_thing(
    group_location_data: CreateGroupThing, session: session_dependency
):
    """
    Create a new group location association in the database.
    """
    return adder(session, GroupThingAssociation, group_location_data)


# ============= Get =============================================
@router.get("", summary="Get groups")
async def get_groups(session: session_dependency,
                     filter_: str =  Query(
                         alias="filter",
                        default=None)
                     ) -> CustomPage[GroupResponse]:
    """
    Retrieve all groups from the database.
    """
    return paginated_all_getter(session, Group, filter_=filter_)


@router.get("/{group_id}", summary="Get group by ID")
async def get_group_by_id(group_id: int, session: session_dependency) -> GroupResponse:
    """
    Retrieve a group by ID from the database.
    """
    return simple_get_by_id(session, Group, group_id)


@router.get(
    "/association/{association_id}",
    summary="Get group-thing association by ID",
)
async def get_group_thing_by_id(association_id: int, session: session_dependency):
    """
    Retrieve a group-thing association by ID from the database.
    """
    return simple_get_by_id(session, GroupThingAssociation, association_id)


# ============= Patch =============================================
@router.patch("/{group_id}", summary="Update a group by ID")
async def update_group(
    group_id: int, group_data: UpdateGroup, session: session_dependency
) -> GroupResponse:
    """
    Update a group by ID in the database.
    """
    return model_patcher(session, Group, group_id, group_data)
    # return adder(session, Group, group_data, id=group_id)


# ============= EOF =============================================
