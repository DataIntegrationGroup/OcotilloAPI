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
from typing import List

from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    amp_admin_dependency,
    admin_dependency,
    editor_dependency,
    amp_viewer_dependency,
    viewer_dependency,
    no_permission_dependency,
    viewer_function,
    amp_viewer_function,
    no_permission_function,
    amp_editor_dependency,
)
from db import adder
from db.engine import get_db_session
from db.location import LocationThingAssociation, Location
from db.thing import Thing, WellScreen
from db.thing import ThingIdLink
from schemas.location import LocationResponse, UpdateLocation
from schemas.thing import (
    CreateThingIdLink,
    CreateWell,
    CreateWellScreen,
    ThingResponse,
    WellResponse,
    WellScreenResponse,
    UpdateThing,
    UpdateWell,
    SpringResponse,
    CreateSpring,
    CreateThing,
    ThingIdLinkResponse,
    UpdateThingIdLink,
    UpdateWellScreen,
)
from services.crud_helper import model_patcher
from services.query_helper import (
    simple_get_by_id,
    paginated_all_getter,
    order_sort_filter,
)
from services.thing_helper import add_thing, get_db_things
from services.validation.well import validate_screens

router = APIRouter(
    prefix="/thing", tags=["thing"], dependencies=[Depends(viewer_function)]
)


@router.get("")
def get_things(
    session: session_dependency,
    thing_id: int = None,
    thing_type: List[str] | str = Query(default=[]),
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
    if thing_id:
        sql = select(Thing).where(Thing.id == thing_id)
        return paginate(query=sql, conn=session)
    else:
        return get_db_things(
            filter_,
            order,
            query,
            session,
            sort,
            thing_type,
            with_location=True,
            within=within,
        )


@router.get(
    "/well", summary="Get all wells", dependencies=[Depends(amp_viewer_function)]
)
async def get_wells(
    session: session_dependency,
    # api_id: str = None,
    # ose_pod_id: str = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
    thing_type: List[str] | str = Query(default="water well"),
    query: str = None,
) -> CustomPage[WellResponse]:
    """
    Retrieve all wells from the database.
    """

    # if api_id:
    #     sql = select(WellThing).where(WellThing.api_id == api_id)
    # elif ose_pod_id:
    #     sql = select(WellThing).where(WellThing.ose_pod_id == ose_pod_id)
    return get_db_things(filter_, order, query, session, sort, thing_type)
    # If no parameters, return all wells
    # return simple_all_getter(session, Well)

    # result = session.execute(sql)
    # return result.scalars().all()


@router.get(
    "/spring", summary="Get all springs", dependencies=[Depends(amp_viewer_function)]
)
async def get_springs(
    session: session_dependency,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
    thing_type: List[str] | str = Query(default="water well"),
) -> CustomPage[SpringResponse]:
    """
    Retrieve all springs from the database.
    """
    return get_db_things(filter_, order, None, session, sort, thing_type)


@router.get(
    "/well-screen",
    summary="Get well screens",
    dependencies=[Depends(amp_viewer_function)],
)
async def get_well_screens(
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
    dependencies=[Depends(amp_viewer_function)],
    summary="Get well screen by ID",
)
async def get_well_screen_by_id(
    session: session_dependency,
    wellscreen_id: int,
) -> WellScreenResponse:
    """
    Retrieve a well screen by ID from the database.
    """
    well_screen = simple_get_by_id(session, WellScreen, wellscreen_id)
    if not well_screen:
        return {"message": "Well screen not found"}
    return well_screen


@router.get("/{thing_id}/id-link", summary="Get thing links by thing ID")
def get_thing_id_links(
    thing_id: int,
    session: session_dependency,
) -> CustomPage[ThingIdLinkResponse]:
    """
    Retrieve all links for a specific thing by its ID.
    """
    sql = select(ThingIdLink).where(ThingIdLink.thing_id == thing_id)
    return paginate(query=sql, conn=session)


@router.get("/id-link/{link_id}", summary="Get thing links by link ID")
def get_thing_id_links(
    link_id: int,
    session: session_dependency,
) -> ThingIdLinkResponse:
    """
    Retrieve all links for a specific thing by its ID.
    """
    return simple_get_by_id(session, ThingIdLink, link_id)


@router.get(
    "/id-link",
    summary="Get all thing links",
)
def get_thing_id_links(
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


#  ===== POST =============


@router.post(
    "/id-link", status_code=status.HTTP_201_CREATED, summary="Create a new thing link"
)
def create_thing_id_link(
    link_data: CreateThingIdLink,
    session: session_dependency,
    user: admin_dependency,
):
    """
    Create a new link between a thing and an alternate ID.
    """
    return adder(session, ThingIdLink, link_data, user=user)


@router.post(
    "/well",
    summary="Create a well",
    status_code=status.HTTP_201_CREATED,
)
def create_well(
    thing_data: CreateWell,
    session: session_dependency,
    user: amp_admin_dependency,
) -> WellResponse:
    """
    Create a new well in the database.
    """
    # print("Creating well with data:", well_data, user)

    return add_thing(session, thing_data, thing_type="water well", user=user)


@router.post(
    "/spring",
    summary="Create a new spring",
    status_code=status.HTTP_201_CREATED,
)
def create_spring(
    thing_data: CreateSpring,
    session: session_dependency,
    user: amp_admin_dependency,
) -> SpringResponse:
    """
    Create a new well in the database.
    """
    return add_thing(session, thing_data, thing_type="spring", user=user)


@router.post(
    "",
    summary="Create a new thing",
    status_code=status.HTTP_201_CREATED,
)
def create_thing(
    thing_data: CreateThing,
    session: session_dependency,
    user: admin_dependency,
) -> ThingResponse:
    """
    Create a new well in the database.
    """
    return add_thing(session, thing_data, user=user)


@router.post(
    "/well-screen",
    summary="Create a new well screen",
    status_code=status.HTTP_201_CREATED,
)
def create_wellscreen(
    session: session_dependency,
    user: amp_admin_dependency,
    well_screen_data: CreateWellScreen = Depends(validate_screens),
) -> WellScreenResponse:
    """
    Create a new well screen in the database.
    """
    return adder(session, WellScreen, well_screen_data, user=user)


@router.patch("/{thing_id}", summary="Update thing")
def update_thing(
    thing_id: int,
    thing_data: UpdateWell | UpdateThing,
    user: editor_dependency,
    session: Session = Depends(get_db_session),
) -> ThingResponse:
    """
    Update an existing thing by ID.
    """

    return model_patcher(session, Thing, thing_id, thing_data, user=user)


@router.patch("/{thing_id}/location", summary="Update thing location")
def update_thing_location(
    thing_id: int,
    location_data: UpdateLocation,
    session: session_dependency,
    user: editor_dependency,
) -> LocationResponse:
    """
    Update the location of an existing thing by ID.
    """

    # get active location associated with the thing
    location_id = session.execute(
        select(LocationThingAssociation.location_id)
        .where(LocationThingAssociation.thing_id == thing_id)
        .order_by(LocationThingAssociation.effective_start.desc())
    ).scalar_one_or_none()

    return model_patcher(session, Location, location_id, location_data, user=user)


@router.patch("/{thing_id}", summary="Update thing")
def update_thing(
    thing_id: int,
    thing_data: UpdateThing,
    session: session_dependency,
    user: editor_dependency,
) -> ThingResponse:
    """
    Update an existing well by ID.
    """
    return model_patcher(session, Thing, thing_id, thing_data, user=user)


@router.patch("/well/{thing_id}", summary="Update well by parent thing ID")
def update_thing(
    thing_id: int,
    thing_data: UpdateWell,
    session: session_dependency,
    user: amp_editor_dependency,
) -> WellResponse:
    """
    Update an existing well by ID.
    """
    return model_patcher(session, Thing, thing_id, thing_data, user=user)


@router.patch("/id-link/{link_id}", summary="Update thing link by ID")
def update_thing_id_link(
    link_id: int,
    link_data: UpdateThingIdLink,
    session: session_dependency,
    user: editor_dependency,
) -> ThingIdLinkResponse:
    return model_patcher(session, ThingIdLink, link_id, link_data, user=user)


@router.patch("/well-screen/{well_screen_id}", summary="Update Well Screen by ID")
def update_thing_id_link(
    well_screen_id: int,
    well_screen_data: UpdateWellScreen,
    session: session_dependency,
    user: editor_dependency,
) -> WellScreenResponse:
    return model_patcher(
        session, WellScreen, well_screen_id, well_screen_data, user=user
    )


# ============= EOF =============================================
