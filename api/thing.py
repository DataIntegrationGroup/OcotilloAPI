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
from fastapi import APIRouter, Query, Request
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import selectinload
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_409_CONFLICT,
)

from api.pagination import CustomPage
from core.app import public_route
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db.deployment import Deployment
from db.thing import Thing, ThingIdLink, WellScreen
from schemas.deployment import DeploymentResponse
from schemas.thing import (
    CreateThingIdLink,
    CreateWell,
    CreateWellScreen,
    ThingResponse,
    WellResponse,
    WellScreenResponse,
    UpdateSpring,
    UpdateWell,
    SpringResponse,
    CreateSpring,
    ThingIdLinkResponse,
    UpdateThingIdLink,
    UpdateWellScreen,
)
from services.crud_helper import model_patcher, model_adder, model_deleter
from services.exceptions_helper import PydanticStyleException
from services.lexicon_helper import get_terms_by_category
from services.query_helper import (
    simple_get_by_id,
    paginated_all_getter,
    order_sort_filter,
)
from services.thing_helper import (
    add_thing,
    patch_thing,
    add_well_screen,
    get_db_things,
    get_thing_of_a_thing_type_by_id,
    modify_well_descriptor_tables,
    WELL_DESCRIPTOR_MODEL_MAP,
)

router = APIRouter(prefix="/thing", tags=["thing"])


def database_error_handler(
    payload: CreateWell | CreateSpring, error: ProgrammingError
) -> None:
    """
    Handle errors raised by the database when adding or updating a thing.
    """

    error_message = error.orig.args[0]["M"]

    if (
        error_message
        == 'insert or update on table "group_thing_association" violates foreign key constraint "group_thing_association_group_id_fkey"'
    ):

        detail = {
            "loc": ["body", "group_id"],
            "msg": f"Group with ID {payload.group_id} not found.",
            "type": "value_error",
            "input": {"group_id": payload.group_id},
        }
    elif (
        error_message
        == 'insert or update on table "location_thing_association" violates foreign key constraint "location_thing_association_location_id_fkey"'
    ):

        detail = {
            "loc": ["body", "location_id"],
            "msg": f"Location with ID {payload.location_id} not found.",
            "type": "value_error",
            "input": {"location_id": payload.location_id},
        }
    elif (
        error_message
        == 'insert or update on table "well_screen" violates foreign key constraint "well_screen_thing_id_fkey"'
    ):
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} not found.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }
    elif (
        error_message
        == 'insert or update on table "well_screen" violates foreign key constraint "well_screen_screen_type_fkey"'
    ):
        valid_screen_types = get_terms_by_category("casing_material")
        valid_screen_types_for_msg = " | ".join(valid_screen_types)
        detail = {
            "loc": ["body", "screen_type"],
            "msg": f"{payload.screen_type} is an invalid screen type. Valid types are: {valid_screen_types_for_msg}.",
            "type": "value_error",
            "input": {"screen_type": payload.screen_type},
        }
    elif (
        error_message
        == 'insert or update on table "thing_id_link" violates foreign key constraint "thing_id_link_thing_id_fkey"'
    ):
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} not found.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }

    raise PydanticStyleException(status_code=HTTP_409_CONFLICT, detail=[detail])


# GET ==========================================================================


@router.get("/water-well", summary="Get all water wells", status_code=HTTP_200_OK)
async def get_water_wells(
    user: viewer_dependency,
    session: session_dependency,
    request: Request,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
    query: str = None,
    name: str = None,
) -> CustomPage[WellResponse]:
    """
    Retrieve all wells from the database.
    """
    thing_type = request.url.path.split("/")[2].replace("-", " ")
    return get_db_things(
        filter_, order, query, session, sort, name=name, thing_type=thing_type
    )


@router.get(
    "/water-well/{thing_id}", summary="Get water well by ID", status_code=HTTP_200_OK
)
async def get_well_by_id(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
    request: Request,
) -> WellResponse:
    """
    Retrieve a water well by ID from the database.
    """
    return get_thing_of_a_thing_type_by_id(session, request, thing_id)


@router.get(
    "/water-well/{thing_id}/well-screen",
    summary="Get well screens by water well ID",
    status_code=HTTP_200_OK,
)
async def get_well_screens_by_well_id(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
    request: Request,
) -> CustomPage[WellScreenResponse]:
    """
    Retrieve all well screens for a specific water well by its ID.
    """
    thing = get_thing_of_a_thing_type_by_id(session, request, thing_id)
    sql = select(WellScreen).where(WellScreen.thing_id == thing.id)
    return paginate(query=sql, conn=session)


@router.get(
    "/well-screen",
    summary="Get well screens",
)
async def get_well_screens(
    user: viewer_dependency,
    session: session_dependency,
    thing_id: int = None,
) -> CustomPage[WellScreenResponse]:
    """
    Retrieve all well screens from the database.
    """
    if thing_id:
        sql = select(WellScreen).where(WellScreen.thing_id == thing_id)
        return paginate(query=sql, conn=session)

    return paginated_all_getter(session, WellScreen)


@router.get(
    "/well-screen/{wellscreen_id}",
    summary="Get well screen by ID",
)
async def get_well_screen_by_id(
    user: viewer_dependency,
    session: session_dependency,
    wellscreen_id: int,
) -> WellScreenResponse:
    """
    Retrieve a well screen by ID from the database.
    """
    well_screen = simple_get_by_id(session, WellScreen, wellscreen_id)
    return well_screen


@router.get("/spring", summary="Get all springs")
async def get_springs(
    user: viewer_dependency,
    session: session_dependency,
    request: Request,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
    query: str = None,
) -> CustomPage[SpringResponse]:
    """
    Retrieve all springs from the database.
    """
    thing_type = request.url.path.split("/")[2].replace("-", " ")
    return get_db_things(filter_, order, query, session, sort, thing_type=thing_type)


@router.get("/spring/{thing_id}", summary="Get spring by ID", status_code=HTTP_200_OK)
async def get_spring_by_id(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
    request: Request,
) -> SpringResponse:
    """
    Retrieve a spring by ID from the database.
    """
    return get_thing_of_a_thing_type_by_id(session, request, thing_id)


@router.get(
    "/id-link",
    summary="Get all thing links",
)
async def get_thing_id_links(
    user: viewer_dependency,
    session: session_dependency,
    filter_: str = Query(alias="filter", default=None),
    sort: str = None,
    order: str = None,
) -> CustomPage[ThingIdLinkResponse]:
    """
    Retrieve all thing links, optionally filtered and sorted.
    """
    sql = select(ThingIdLink)
    sql = order_sort_filter(sql, ThingIdLink, sort=sort, order=order, filter_=filter_)

    return paginate(query=sql, conn=session)


@public_route
@router.get("/id-link/{link_id}", summary="Get thing links by link ID")
async def get_thing_id_links(
    user: viewer_dependency,
    link_id: int,
    session: session_dependency,
) -> ThingIdLinkResponse:
    """
    Retrieve all links for a specific thing by its ID.
    """
    return simple_get_by_id(session, ThingIdLink, link_id)


@public_route
@router.get("", summary="Get all things", status_code=HTTP_200_OK)
async def get_things(
    user: viewer_dependency,
    session: session_dependency,
    # thing_id: int = None,
    within: str = None,
    query: str = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(
        default=None,
        alias="filter",
    ),
) -> CustomPage[ThingResponse]:
    """
    Retrieve all things or filter by type.
    """

    return get_db_things(
        filter_,
        order,
        query,
        session,
        sort,
        within=within,
    )


@router.get("/{thing_id}", summary="Get thing by ID", status_code=HTTP_200_OK)
async def get_thing_by_id(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
    request: Request,
) -> ThingResponse:
    """
    Retrieve a thing by ID from the database.
    """
    thing = simple_get_by_id(session, Thing, thing_id)
    return thing


@router.get("/{thing_id}/id-link", summary="Get thing links by thing ID")
async def get_thing_id_links(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
) -> CustomPage[ThingIdLinkResponse]:
    """
    Retrieve all links for a specific thing by its ID.
    """
    thing = simple_get_by_id(session, Thing, thing_id)
    sql = select(ThingIdLink).where(ThingIdLink.thing_id == thing.id)
    return paginate(query=sql, conn=session)


@router.get("/{thing_id}/deployment", summary="Get deployments by thing ID")
async def get_thing_deployments(
    user: viewer_dependency,
    thing_id: int,
    session: session_dependency,
) -> CustomPage[DeploymentResponse]:
    """
    Retrieve all deployments for a specific thing by its ID.
    """
    thing = simple_get_by_id(session, Thing, thing_id)
    sql = select(Deployment).where(Deployment.thing_id == thing.id)
    sql = sql.options(selectinload(Deployment.sensor))
    return paginate(query=sql, conn=session)


#  POST ========================================================================


@router.post(
    "/id-link", status_code=HTTP_201_CREATED, summary="Create a new thing link"
)
async def create_thing_id_link(
    link_data: CreateThingIdLink,
    session: session_dependency,
    user: admin_dependency,
) -> ThingIdLinkResponse:
    """
    Create a new link between a thing and an alternate ID.
    """
    try:
        return model_adder(session, ThingIdLink, link_data, user=user)
    except ProgrammingError as e:
        database_error_handler(link_data, e)


@router.post(
    "/water-well",
    summary="Create a water well",
    status_code=HTTP_201_CREATED,
)
async def create_well(
    thing_data: CreateWell,
    session: session_dependency,
    request: Request,
    user: admin_dependency,
) -> WellResponse:
    """
    Create a new water well in the database.
    """
    try:
        thing = add_thing(session=session, data=thing_data, request=request, user=user)
        modify_well_descriptor_tables(session, thing, thing_data, user)
        return thing
    except ProgrammingError as e:
        database_error_handler(thing_data, e)


@router.post(
    "/spring",
    summary="Create a new spring",
    status_code=HTTP_201_CREATED,
)
async def create_spring(
    thing_data: CreateSpring,
    session: session_dependency,
    request: Request,
    user: admin_dependency,
) -> SpringResponse:
    """
    Create a new well in the database.
    """
    try:
        return add_thing(session=session, data=thing_data, request=request, user=user)
    except ProgrammingError as e:
        database_error_handler(thing_data, e)


@router.post(
    "/well-screen",
    summary="Create a new well screen",
    status_code=HTTP_201_CREATED,
)
async def create_wellscreen(
    session: session_dependency,
    user: admin_dependency,
    well_screen_data: CreateWellScreen,
) -> WellScreenResponse:
    """
    Create a new well screen in the database.
    """
    try:
        return add_well_screen(session, well_screen_data, user=user)
    except ProgrammingError as e:
        database_error_handler(well_screen_data, e)
    except PydanticStyleException as e:
        raise e


# PATCH ========================================================================


@router.patch(
    "/water-well/{thing_id}",
    summary="Update well by parent thing ID",
    status_code=HTTP_200_OK,
)
async def update_water_well(
    thing_id: int,
    thing_data: UpdateWell,
    session: session_dependency,
    user: editor_dependency,
    request: Request,
) -> WellResponse:
    """
    Update an existing well by ID.
    """
    well_descriptor_data = thing_data.model_copy(deep=True)

    # remove these fields from payload otherwise patch_thing will try to process
    # and raise an error because they are not found in the Thing model
    for field in WELL_DESCRIPTOR_MODEL_MAP.keys():
        if hasattr(thing_data, field):
            delattr(thing_data, field)

    thing = patch_thing(session, request, thing_id, thing_data, user=user)
    modify_well_descriptor_tables(session, thing, well_descriptor_data, user)

    return thing


@router.patch(
    "/spring/{thing_id}",
    summary="Update spring by parent thing ID",
    status_code=HTTP_200_OK,
)
async def update_spring(
    thing_id: int,
    thing_data: UpdateSpring,
    session: session_dependency,
    user: editor_dependency,
    request: Request,
) -> SpringResponse:
    """
    Update an existing spring by ID.
    """
    return patch_thing(session, request, thing_id, thing_data, user=user)


@router.patch(
    "/id-link/{link_id}", summary="Update thing link by ID", status_code=HTTP_200_OK
)
async def update_thing_id_link(
    link_id: int,
    link_data: UpdateThingIdLink,
    session: session_dependency,
    user: editor_dependency,
) -> ThingIdLinkResponse:
    return model_patcher(session, ThingIdLink, link_id, link_data, user=user)


@router.patch(
    "/well-screen/{well_screen_id}",
    summary="Update Well Screen by ID",
    status_code=HTTP_200_OK,
)
async def update_well_screen(
    well_screen_id: int,
    well_screen_data: UpdateWellScreen,
    session: session_dependency,
    user: editor_dependency,
) -> WellScreenResponse:

    # TODO: add validation
    return model_patcher(
        session, WellScreen, well_screen_id, well_screen_data, user=user
    )


# DELETE =======================================================================


@router.delete(
    "/{thing_id}", summary="Delete thing by ID", status_code=HTTP_204_NO_CONTENT
)
async def delete_thing(
    thing_id: int,
    session: session_dependency,
    user: admin_dependency,
) -> None:
    """
    Delete a thing by ID.
    """
    return model_deleter(session, Thing, thing_id)


@router.delete(
    "/well-screen/{well_screen_id}",
    summary="Delete well screen by ID",
    status_code=HTTP_204_NO_CONTENT,
)
async def delete_well_screen(
    well_screen_id: int,
    session: session_dependency,
    user: admin_dependency,
) -> None:
    """
    Delete a well screen by ID.
    """
    return model_deleter(session, WellScreen, well_screen_id)


@router.delete(
    "/id-link/{link_id}",
    summary="Delete thing link by ID",
    status_code=HTTP_204_NO_CONTENT,
)
async def delete_thing_id_link(
    link_id: int,
    session: session_dependency,
    user: admin_dependency,
) -> None:
    """
    Delete a thing link by ID.
    """
    return model_deleter(session, ThingIdLink, link_id)


# ============= EOF =============================================
