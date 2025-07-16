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
from typing import List, Annotated, Union
from shapely.geometry import mapping
from shapely import wkb
from fastapi import APIRouter, Depends, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from db import (
    WellThing,
    WellScreen,
    SpringThing,
    adder,
    LocationThingAssociation,
    Thing,
)
from db.engine import get_db_session
from db.group import GroupThingAssociation, Group
from db.thing.thing import ThingIdLink
from schemas.base_create import CreateSpring
from schemas.base_get import GetWell
from schemas.base_responses import SpringResponse
from schemas.create.thing import CreateThingIdLink, CreateWell, CreateWellScreen
from schemas.response.thing import WellResponse, WellScreenResponse, ThingResponse, FeatureCollectionResponse, Feature
from services.query_helper import (
    make_query,
    simple_all_getter,
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

@router.get('/')
def get_things(thing_type: Annotated[str, Query(title="thing type", description="thing type", alias='type')] = None,
               group: Annotated[str, Query(title="group", description="group", alias='group')] = None,
               response_format: Annotated[str, Query(title="response format", description="response format", alias='format')] = 'json',
               session: Session = Depends(get_db_session)) -> Union[List[ThingResponse], FeatureCollectionResponse]:
    """
    Retrieve all things or filter by type.
    """
    if thing_type == 'well':
        sql = select(Thing).join(WellThing)
    elif thing_type == 'spring':
        sql = select(Thing).join(SpringThing)
    else:
        sql = select(Thing)

    if group:
        sql = sql.join(GroupThingAssociation).join(Group).where(Group.name == group)

    if response_format == 'geojson':
        #todo: implement geojson response
        def make_feature(thing: Thing) -> Feature:

            #todo: get latest location
            geometry = thing.locations[0].point
            # Convert geometry to GeoJSON format

            geojson_geometry = wkb_to_geojson(geometry)
            properties = {
                "id": thing.id,
                "name": thing.name,
                "type": thing_type,
                "group": group,
            }
            return Feature(geometry=geojson_geometry, properties=properties)

        things = session.scalars(sql).all()
        features = [make_feature(thing) for thing in things]
        return FeatureCollectionResponse(features=features)
    else:
        # return paginate(query=sql, conn=session)
        return session.scalars(sql).all()


@router.get("/well", summary="Get all wells")
async def get_wells(
    # api_id: str = None,
    # ose_pod_id: str = None,
    query: str = None,
    session: Session = Depends(get_db_session),
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
    session: Session = Depends(get_db_session),
) -> CustomPage[WellScreenResponse]:
    """
    Retrieve all well screens from the database.
    """
    return paginated_all_getter(session, WellScreen)


@router.get(
    "/spring",
)
async def get_springs(
    session: Session = Depends(get_db_session),
) -> CustomPage[SpringResponse]:
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
def create_thing_id_link(
    link_data: CreateThingIdLink,
    session: Session = Depends(get_db_session),
):
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
    well_screen_data: CreateWellScreen = Depends(validate_screens),
    session: Session = Depends(get_db_session),
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


# ============= EOF =============================================
