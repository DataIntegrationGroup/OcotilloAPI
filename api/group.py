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

from fastapi import APIRouter, Query
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db.group import Group
from schemas.group import UpdateGroup, CreateGroup, GroupResponse
from services.crud_helper import model_patcher, model_deleter, model_adder
from services.group_helper import (
    add_thing_to_group,
    get_well_counts_by_group_id,
    group_to_response,
    paginated_groups_getter,
    remove_thing_from_group,
)
from services.query_helper import simple_get_by_id

router = APIRouter(prefix="/group", tags=["group"])

# POST =========================================================================


@router.post("", summary="Create a new group", status_code=HTTP_201_CREATED)
def create_group(
    group_data: CreateGroup, session: session_dependency, user: admin_dependency
) -> GroupResponse:
    """
    Create a new group in the database.
    """
    return model_adder(session, Group, group_data, user=user)


@router.post(
    "/{group_id}/things/{thing_id}",
    summary="Add a thing to a group",
    status_code=HTTP_201_CREATED,
)
def add_thing_to_group_route(
    group_id: int,
    thing_id: int,
    session: session_dependency,
    user: admin_dependency,
):
    """
    Associate a thing (e.g. a water well) with a group (project).
    Returns 409 if the association already exists.
    """
    return add_thing_to_group(session, group_id, thing_id, user)


# ============= Get =============================================
@router.get("", summary="Get groups")
def get_groups(
    user: viewer_dependency,
    session: session_dependency,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[GroupResponse]:
    """
    Retrieve all groups from the database.
    """
    return paginated_groups_getter(session, filter_=filter_)


@router.get("/{group_id}", summary="Get group by ID")
def get_group_by_id(
    user: viewer_dependency, group_id: int, session: session_dependency
) -> GroupResponse:
    """
    Retrieve a group by ID from the database.
    """
    group = simple_get_by_id(session, Group, group_id)
    counts = get_well_counts_by_group_id(session, [group.id])
    return group_to_response(group, counts.get(group.id, 0))


# ============= Patch =============================================
@router.patch("/{group_id}", summary="Update a group by ID")
def update_group(
    user: editor_dependency,
    group_id: int,
    group_data: UpdateGroup,
    session: session_dependency,
) -> GroupResponse:
    """
    Update a group by ID in the database.
    """
    return model_patcher(session, Group, group_id, group_data, user=user)


# DELETE =======================================================================
@router.delete(
    "/{group_id}/things/{thing_id}",
    summary="Remove a thing from a group",
    status_code=HTTP_204_NO_CONTENT,
)
def remove_thing_from_group_route(
    group_id: int,
    thing_id: int,
    session: session_dependency,
    user: admin_dependency,
):
    """
    Remove the association between a thing and a group.
    Returns 404 if the association does not exist.
    """
    remove_thing_from_group(session, group_id, thing_id, user)


@router.delete(
    "/{group_id}", summary="Delete a group by ID", status_code=HTTP_204_NO_CONTENT
)
def delete_group(user: admin_dependency, group_id: int, session: session_dependency):
    return model_deleter(session, Group, group_id, user=user)


# ============= EOF =============================================
