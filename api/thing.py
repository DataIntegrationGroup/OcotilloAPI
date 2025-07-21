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
from shapely.geometry import mapping
from shapely import wkb
from fastapi import APIRouter, Depends
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import (
    WellThing,
    WellScreen,
    SpringThing,
    adder,
    LocationThingAssociation,
    Thing,
    Location,
)
from db.engine import get_db_session
from db.thing.thing import ThingIdLink
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
)
from schemas_v2.location import LocationResponse, UpdateLocation

from services.crud_helper import model_patcher
from services.query_helper import (
    make_query,
    simple_get_by_id,
    paginated_all_getter,
)
from services.thing_helper import add_well, add_spring
from services.validation.well import validate_screens


def wkb_to_geojson(wkb_element):
    if wkb_element is None:
        return None
    geom = wkb.loads(bytes(wkb_element.data))
    return mapping(geom)


router = APIRouter(prefix="/thing", tags=["thing"])


@router.get("/")
def get_things(
    session: session_dependency,
) -> CustomPage[ThingResponse]:
    """
    Retrieve all things or filter by type.
    """
    # if thing_type == "well":
    #     sql = select(Thing).join(WellThing)
    # elif thing_type == "spring":
    #     sql = select(Thing).join(SpringThing)
    # else:
    #     sql = select(Thing)
    #
    # if group:
    #     sql = sql.join(GroupThingAssociation).join(Group).where(Group.name == group)
    #
    # if response_format == "geojson":
    #     # todo: implement geojson response
    #     def make_feature(thing: Thing) -> Feature:
    #
    #         # todo: get latest location
    #         geometry = thing.locations[0].point
    #         # Convert geometry to GeoJSON format
    #
    #         geojson_geometry = wkb_to_geojson(geometry)
    #         properties = {
    #             "id": thing.id,
    #             "name": thing.name,
    #             "type": thing_type,
    #             "group": group,
    #         }
    #         return Feature(geometry=geojson_geometry, properties=properties)
    #
    #     things = session.scalars(sql).all()
    #     features = [make_feature(thing) for thing in things]
    #     return FeatureCollectionResponse(features=features)
    # else:
    #     # return paginate(query=sql, conn=session)
    #     return session.scalars(sql).all()
    return paginated_all_getter(session, Thing)


@router.get("/well", summary="Get all wells")
async def get_wells(
    # api_id: str = None,
    # ose_pod_id: str = None,
    session: session_dependency,
    query: str = None,
) -> CustomPage[WellResponse]:
    """
    Retrieve all wells from the database.
    """

    # if api_id:
    #     sql = select(WellThing).where(WellThing.api_id == api_id)
    # elif ose_pod_id:
    #     sql = select(WellThing).where(WellThing.ose_pod_id == ose_pod_id)
    if query:
        sql = select(WellThing).where(make_query(WellThing, query))
    else:
        sql = select(WellThing)

    return paginate(query=sql, conn=session)
    # If no parameters, return all wells
    # return simple_all_getter(session, Well)

    # result = session.execute(sql)
    # return result.scalars().all()


@router.get(
    "/well/screen",
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
    "/spring",
)
async def get_springs(session: session_dependency) -> CustomPage[SpringResponse]:
    """
    Retrieve all springs from the database.
    """
    return paginated_all_getter(session, SpringThing)


@router.get("/spring/{spring_id}", summary="Get spring by ID")
async def get_spring_by_id(
    spring_id: int, session: Session = Depends(get_db_session)
) -> SpringResponse:
    """
    Retrieve a spring by ID from the database.
    """
    return simple_get_by_id(session, SpringThing, spring_id)


@router.get("/well/{well_id}", summary="Get well by ID")
async def get_well_by_id(
    well_id: int, session: Session = Depends(get_db_session)
) -> WellResponse:
    """
    Retrieve a well by ID from the database.
    """
    well = simple_get_by_id(session, WellThing, well_id)
    if not well:
        return {"message": "Well not found"}
    return well


@router.get(
    "/well/screen/{wellscreen_id}",
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
    summary="Create a new well",
    status_code=status.HTTP_201_CREATED,
)
def create_well(
    well_data: CreateWell, session: Session = Depends(get_db_session)
) -> WellResponse:
    """
    Create a new well in the database.
    """
    well = add_well(session, well_data)
    return well


@router.post(
    "/well/screen",
    summary="Create a new well screen",
    status_code=status.HTTP_201_CREATED,
)
def create_wellscreen(
    session: session_dependency,
    well_screen_data: CreateWellScreen = Depends(validate_screens),
) -> WellScreenResponse:
    """
    Create a new well screen in the database.
    """
    return adder(session, WellScreen, well_screen_data)


@router.post(
    "/spring", summary="Create a new spring", status_code=status.HTTP_201_CREATED
)
def create_spring(
    spring_data: CreateSpring, session: Session = Depends(get_db_session)
) -> SpringResponse:
    """
    Create a new spring in the database.
    """
    return add_spring(session, spring_data)
    # return adder(session, SpringThing, spring_data)


@router.patch("/{thing_id}", summary="Update thing")
def update_thing(
    thing_id: int,
    thing_data: UpdateThing,
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


@router.patch("/{thing_id}/well", summary="Update well by parent thing ID")
def update_well(
    thing_id: int,
    well_data: UpdateWell,
    session: session_dependency,
) -> WellResponse:
    """
    Update an existing well by ID.
    """

    # get the WellThing associated with the Thing ID
    well_thing_id = session.execute(
        select(WellThing.id).join(Thing).where(Thing.id == thing_id)
    ).scalar_one_or_none()

    return model_patcher(session, WellThing, well_thing_id, well_data)


@router.patch("/well/{well_id}", summary="Update well by well ID")
def update_well_by_id(
    well_id: int,
    well_data: UpdateWell,
    session: session_dependency,
) -> WellResponse:
    """
    Update an existing well by its ID.
    """
    return model_patcher(session, WellThing, well_id, well_data)


# ============= EOF =============================================
