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

from fastapi import APIRouter, Depends
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
from schemas.base_create import CreateSpring
from schemas.base_get import GetWell
from schemas.base_responses import SpringResponse
from schemas.create.well import CreateWell, CreateWellScreen
from schemas.response.well import WellResponse, WellScreenResponse
from services.query_helper import make_query, simple_all_getter, simple_get_by_id
from services.thing_helper import add_well
from services.validation.well import validate_screens

router = APIRouter(prefix="/thing", tags=["thing"])


@router.get("/well", response_model=CustomPage[WellResponse], summary="Get all wells")
async def get_wells(
    # api_id: str = None,
    # ose_pod_id: str = None,
    query: str = None,
    session: Session = Depends(get_db_session),
):
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
    "/well/screen", response_model=List[WellScreenResponse], summary="Get well screens"
)
async def get_well_screens(session: Session = Depends(get_db_session)):
    """
    Retrieve all well screens from the database.
    """
    return simple_all_getter(session, WellScreen)


@router.get(
    "/spring",
    response_model=List[SpringResponse],
)
async def get_springs(session: Session = Depends(get_db_session)):
    """
    Retrieve all springs from the database.
    """
    return simple_all_getter(session, SpringThing)


@router.get(
    "/spring/{spring_id}", response_model=SpringResponse, summary="Get spring by ID"
)
async def get_spring_by_id(spring_id: int, session: Session = Depends(get_db_session)):
    """
    Retrieve a spring by ID from the database.
    """
    spring = simple_get_by_id(session, SpringThing, spring_id)
    if not spring:
        return {"message": "Spring not found"}
    return spring


@router.get("/well/{well_id}", response_model=WellResponse, summary="Get well by ID")
async def get_well_by_id(well_id: int, session: Session = Depends(get_db_session)):
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
):
    """
    Retrieve a well screen by ID from the database.
    """
    well_screen = simple_get_by_id(session, WellScreen, wellscreen_id)
    if not well_screen:
        return {"message": "Well screen not found"}
    return well_screen


#  ===== POST =============
@router.post(
    "/well",
    response_model=GetWell,
    summary="Create a new well",
    status_code=status.HTTP_201_CREATED,
)
def create_well(well_data: CreateWell, session: Session = Depends(get_db_session)):
    """
    Create a new well in the database.
    """
    data = well_data.model_dump()
    well = add_well(session, data)
    return well


@router.post(
    "/well/screen",
    summary="Create a new well screen",
    status_code=status.HTTP_201_CREATED,
)
def create_wellscreen(
    well_screen_data: CreateWellScreen = Depends(validate_screens),
    session: Session = Depends(get_db_session),
):
    """
    Create a new well screen in the database.
    """
    return adder(session, WellScreen, well_screen_data)


@router.post(
    "/spring", summary="Create a new spring", status_code=status.HTTP_201_CREATED
)
def create_spring(
    spring_data: CreateSpring, session: Session = Depends(get_db_session)
):
    """
    Create a new spring in the database.
    """
    return adder(session, SpringThing, spring_data)


# ============= EOF =============================================
