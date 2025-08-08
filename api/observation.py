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

from fastapi import APIRouter, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import Sample
from db.observation import Observation
from schemas.observation import (
    CreateGroundwaterLevelObservation,
    GroundwaterLevelObservationResponse,
    CreateWaterChemistryObservation,
)
from services.observation_helper import add_observation
from services.query_helper import order_sort_filter

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
    return add_observation(session, obs_data)


@router.post("/water-chemistry", status_code=HTTP_201_CREATED)
def add_water_chemistry_observation(
    obs_data: CreateWaterChemistryObservation,
    session: session_dependency,
):
    """
    Add a new water chemistry observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    return add_observation(session, obs_data)


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
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    polygon: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[GroundwaterLevelObservationResponse]:
    """
    Retrieve all groundwater level observations from the database.
    """
    sql = select(Observation)
    sql = sql.where(Observation.observed_property == "groundwater level")
    if thing_id is not None:
        sql = sql.join(Sample)
        sql = sql.where(Sample.thing_id == thing_id)
    if sample_id is not None:
        sql = sql.where(Observation.sample_id == sample_id)
    if sensor_id is not None:
        sql = sql.where(Observation.sensor_id == sensor_id)

    if start_time:
        sql = sql.where(Observation.observation_datetime >= start_time)
    if end_time:
        sql = sql.where(Observation.observation_datetime <= end_time)

    sql = order_sort_filter(sql, Observation, sort, order, filter_)
    return paginate(query=sql, conn=session)


# ============= EOF =============================================
