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
from typing import Annotated, List

from pydantic import Field
from shapely import wkb
from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from db import adder

from db.thing import ThingIdLink, Thing, WellScreen
from db.location import LocationThingAssociation, Location
from core.dependencies import (
    session_dependency,
    well_user_dependency,
)
from db.engine import get_db_session
from db.thing import ThingIdLink
from schemas_v2.thing import (
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
)
from schemas_v2.location import LocationResponse, UpdateLocation

from services.crud_helper import model_patcher
from services.query_helper import (
    make_query,
    simple_get_by_id,
    paginated_all_getter,
    order_sort_filter,
)
from services.thing_helper import add_thing, get_db_things
from services.validation.well import validate_screens


def wkb_to_geojson(wkb_element):
    if wkb_element is None:
        return None
    geom = wkb.loads(bytes(wkb_element.data))
    return mapping(geom)


router = APIRouter(prefix="/thing", tags=["thing"])


@router.get("")
def get_things(
    session: session_dependency,
    thing_id: int = None,
    thing_type: List[str] | str = Query(default=[]),
    query: str = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(..., alias='filter', ),
) -> CustomPage[ThingResponse]:
    """
    Retrieve all things or filter by type.
    """
    if thing_id:
        sql = select(Thing).where(Thing.id == thing_id)
        return paginate(query=sql, conn=session)
    else:
        return get_db_things(filter_, order, query, session, sort, thing_type)


@router.get("/well", summary="Get all wells")
async def get_wells(
    session: session_dependency,
    # api_id: str = None,
    # ose_pod_id: str = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias='filter', default=None),
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


@router.get("/spring", summary="Get all springs")
async def get_springs(
    session: session_dependency,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias='filter', default=None),
    thing_type: List[str] | str = Query(default="water well"),
) -> CustomPage[SpringResponse]:
    """
    Retrieve all springs from the database.
    """
    return get_db_things(filter_, order, None, session, sort, thing_type)


@router.get(
    "/well-screen",
    summary="Get well screens",
)
async def get_well_screens(
    session: session_dependency,
) -> CustomPage[WellScreenResponse]:
    """
    Retrieve all well screens from the database.
    """
    return paginated_all_getter(session, WellScreen)


@router.get(
    "/well-screen/{wellscreen_id}",
)
async def get_well_screen_by_id(
    wellscreen_id: int, session: Session = Depends(get_db_session)
) -> WellScreenResponse:
    """
    Retrieve a well screen by ID from the database.
    """
    well_screen = simple_get_by_id(session, WellScreen, wellscreen_id)
    if not well_screen:
        return {"message": "Well screen not found"}
    return well_screen


#  ===== POST =============


@router.post(
    "/link", status_code=status.HTTP_201_CREATED, summary="Create a new thing link"
)
def create_thing_id_link(link_data: CreateThingIdLink, session: session_dependency):
    """
    Create a new link between a thing and an alternate ID.
    """
    return adder(session, ThingIdLink, link_data)


@router.post(
    "/well",
    summary="Create a well",
    status_code=status.HTTP_201_CREATED,
)
def create_well(
    thing_data: CreateWell,
    session: Session = Depends(get_db_session),
    user=well_user_dependency,
) -> WellResponse:
    """
    Create a new well in the database.
    """
    # print("Creating well with data:", well_data, user)

    return add_thing(session, thing_data, thing_type="water well")


@router.post(
    "/spring",
    summary="Create a new spring",
    status_code=status.HTTP_201_CREATED,
)
def create_spring(
    thing_data: CreateSpring,
    session: session_dependency,
    user=well_user_dependency,
) -> SpringResponse:
    """
    Create a new well in the database.
    """
    return add_thing(session, thing_data, thing_type="spring")


@router.post(
    "",
    summary="Create a new thing",
    status_code=status.HTTP_201_CREATED,
)
def create_thing(
    thing_data: CreateThing,
    session: session_dependency,
    user=well_user_dependency,
) -> ThingResponse:
    """
    Create a new well in the database.
    """
    return add_thing(session, thing_data)


@router.post(
    "/well-screen",
    summary="Create a new well screen",
    status_code=status.HTTP_201_CREATED,
)
def create_wellscreen(
    session: session_dependency,
    user: well_user_dependency,
    well_screen_data: CreateWellScreen = Depends(validate_screens),
) -> WellScreenResponse:
    """
    Create a new well screen in the database.
    """
    return adder(session, WellScreen, well_screen_data)


@router.patch("/{thing_id}", summary="Update thing")
def update_thing(
    thing_id: int,
    thing_data: UpdateWell | UpdateThing,
    session: Session = Depends(get_db_session),
) -> ThingResponse:
    """
    Update an existing thing by ID.
    """

    return model_patcher(session, Thing, thing_id, thing_data)


@router.patch("/{thing_id}/location", summary="Update thing location")
def update_thing_location(
    thing_id: int,
    location_data: UpdateLocation,
    session: session_dependency,
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

    return model_patcher(session, Location, location_id, location_data)


@router.patch("/{thing_id}", summary="Update well by parent thing ID")
def update_thing(
    thing_id: int,
    thing_data: UpdateWell,
    session: session_dependency,
) -> WellResponse:
    """
    Update an existing well by ID.
    """
    return model_patcher(session, Thing, thing_id, thing_data)


# ============= EOF =============================================
