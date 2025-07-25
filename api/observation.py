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
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder, Thing, Location, LocationThingAssociation
from db.engine import get_db_session
# from db.observation.geothermal import GeothermalObservation
# from db.observation.groundwaterlevel import GroundwaterLevelObservation
from db.observation import Observation
from db.series.series import Series
from schemas_v2.observation import (
    # CreateObservation,
    CreateGroundwaterLevelObservation,
    # CreateGeothermalObservation,
    # CreateGroundwaterLevelObservationDirect,
    # CreateGeothermalObservationDirect,
    ObservationResponse,
    GroundwaterLevelObservationResponse,
    # GeothermalObservationResponse,
)
from services.geospatial_helper import make_within_wkt
from services.observation_helper import add_observation
from services.query_helper import paginated_all_getter

router = APIRouter(prefix="/observation", tags=["observation"])

# ============= Post =============================================
@router.post("/groundwater-level", status_code=HTTP_201_CREATED)
def add_groundwater_level_observation(
    obs_data: CreateGroundwaterLevelObservation,
    session: session_dependency,
):
    """
    Add a new groundwater observation to the database.
    """
    return add_observation(session, obs_data, 'groundwater-level')

#
# @router.post("/geothermal", status_code=HTTP_201_CREATED)
# def add_geothermal_observation(
#     obs_data: CreateGeothermalObservation | CreateGeothermalObservationDirect,
#     session: session_dependency,
# ):
#     """
#     Add a new geothermal observation to the database.
#     This endpoint is currently a placeholder and does not implement any functionality.
#     """
#     if isinstance(obs_data, CreateGeothermalObservationDirect):
#         return direct_adder(session, GeothermalObservation, obs_data)
#     else:
#         return adder(session, GeothermalObservation, obs_data)


# ============= Get ==============================================
@router.get(
    "/groundwater-level",
)
def get_groundwater_level_observations(
    session: session_dependency,
    series_id: int | None = None,
    thing_id: int | None = None,
    polygon: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> CustomPage[GroundwaterLevelObservationResponse]:
    """
    Retrieve all groundwater level observations from the database.
    """
    if series_id is not None:
        sql = (
            select(Observation)
            .where(Observation.series_id == series_id)
        )
        return paginate(query=sql, conn=session)
    elif thing_id is not None:
        sql = (
            select(Observation)
            .join(Series)
            .join(Thing)
            .where(Thing.id == thing_id)
        )
        return paginate(query=sql, conn=session)
    elif polygon is not None:
        sql = (
            select(Observation)
            .join(Series)
            .join(Thing)
            .join(LocationThingAssociation)
            .join(Location)
        )
        sql = make_within_wkt(sql, polygon)
        return paginate(query=sql, conn=session)
    elif start_time is not None and end_time is not None:
        sql = (
            select(Observation)
            .where(
                Observation.observation_timestamp >= start_time,
                Observation.observation_timestamp <= end_time,
            )
        )
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, Observation)

# ============= EOF =============================================
