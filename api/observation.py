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
import functools

from fastapi import APIRouter, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND

from api.pagination import CustomPage
from core.dependencies import session_dependency, amp_admin_dependency, admin_dependency
from db import Sample, Observation, adder
from schemas.observation import (
    CreateGroundwaterLevelObservation,
    GroundwaterLevelObservationResponse,
    CreateWaterChemistryObservation,
    WaterChemistryObservationResponse,
    CreateGeothermalObservation,
    GeothermalObservationResponse,
    ObservationResponse,
)
from services.exceptions_helper import PydanticStyleException
from services.query_helper import order_sort_filter, simple_get_by_id

router = APIRouter(prefix="/observation", tags=["observation"])


# ============= Post =============================================
@router.post("/groundwater-level", status_code=HTTP_201_CREATED)
def add_groundwater_level_observation(
    obs_data: CreateGroundwaterLevelObservation,
    session: session_dependency,
    user: amp_admin_dependency,
) -> GroundwaterLevelObservationResponse:
    """
    Add a new groundwater observation to the database.
    """
    return adder(session, Observation, obs_data, user=user)


@router.post("/water-chemistry", status_code=HTTP_201_CREATED)
def add_water_chemistry_observation(
    obs_data: CreateWaterChemistryObservation,
    session: session_dependency,
    user: amp_admin_dependency,
) -> WaterChemistryObservationResponse:
    """
    Add a new water chemistry observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    return adder(session, Observation, obs_data, user=user)


@router.post("/geothermal", status_code=HTTP_201_CREATED)
def add_geothermal_observation(
    obs_data: CreateGeothermalObservation,
    session: session_dependency,
    user: admin_dependency,
) -> GeothermalObservationResponse:
    """
    Add a new geothermal observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    return adder(session, Observation, obs_data, user=user)


# ============= Get ==============================================


def specify_observation_class(observation_class: str | None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sql, session = func(*args, **kwargs)
            if observation_class == "groundwater level":
                sql = sql.where(Observation.observed_property == "groundwater level")
            elif observation_class == "water chemistry":
                sql = sql.where(Observation.observed_property != "groundwater level")
                sql = sql.where(Observation.observed_property != "temperature")
            elif observation_class == "geothermal":
                sql = sql.where(Observation.observed_property == "temperature")
            return paginate(query=sql, conn=session)

        return wrapper

    return decorator


def get_observations(
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> tuple:
    """
    Retrieve all observations
    """
    sql = select(Observation)
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

    if not order:
        sql = sql.order_by(Observation.observation_datetime.desc())

    return sql, session


@router.get("/groundwater-level", summary="Get groundwater level observations")
@specify_observation_class(observation_class="groundwater level")
def get_groundwater_level_observations(
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[GroundwaterLevelObservationResponse]:
    """
    Retrieve all groundwater level observations from the database.
    """
    return get_observations(
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get(
    "/groundwater-level/{observation_id}",
    summary="Get groundwater level observation by ID",
)
def get_groundwater_level_observation_by_id(
    session: session_dependency, observation_id: int
) -> GroundwaterLevelObservationResponse:
    observation = simple_get_by_id(session, Observation, observation_id)
    if observation.observed_property != "groundwater level":
        if observation.observed_property == "temperature":
            url = f"/observation/geothermal/{observation_id}"
        else:
            url = f"/observation/water-chemistry/{observation_id}"
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "msg": f"Observation with ID {observation_id} is not a groundwater level observation. To retrieve it, use the following URL: {url}",
                    "type": "value_error",
                    "input": {"observation_id": observation_id},
                }
            ],
        )
    else:
        return observation


@router.get("/water-chemistry", summary="Get water chemistry observations")
@specify_observation_class(observation_class="water chemistry")
def get_water_chemistry_observations(
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[WaterChemistryObservationResponse]:
    """
    Retrieve all water chemistry observations from the database.
    """
    return get_observations(
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get(
    "/water-chemistry/{observation_id}", summary="Get water chemistry observation by ID"
)
def get_water_chemistry_observation_by_id(
    session: session_dependency, observation_id: int
) -> WaterChemistryObservationResponse:
    observation = simple_get_by_id(session, Observation, observation_id)
    if observation.observed_property in ("groundwater level", "temperature"):
        if observation.observed_property == "groundwater level":
            url = f"/observation/groundwater-level/{observation_id}"
        else:
            url = f"/observation/geothermal/{observation_id}"
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "msg": f"Observation with ID {observation_id} is not a water chemistry observation. To retrieve it, use the following URL: {url}",
                    "type": "value_error",
                    "input": {"observation_id": observation_id},
                }
            ],
        )
    else:
        return observation


@router.get("/geothermal", summary="Get geothermal observations")
@specify_observation_class(observation_class="geothermal")
def get_geothermal_observations(
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[GeothermalObservationResponse]:
    """
    Retrieve all geothermal observations from the database.
    """
    return get_observations(
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get("/geothermal/{observation_id}", summary="Get geothermal observation by ID")
def get_geothermal_observation_by_id(
    session: session_dependency, observation_id: int
) -> GeothermalObservationResponse:
    observation = simple_get_by_id(session, Observation, observation_id)
    if observation.observed_property != "temperature":
        if observation.observed_property == "groundwater level":
            url = f"/observation/groundwater-level/{observation_id}"
        else:
            url = f"/observation/water-chemistry/{observation_id}"
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "msg": f"Observation with ID {observation_id} is not a geothermal observation. To retrieve it, use the following URL: {url}",
                    "type": "value_error",
                    "input": {"observation_id": observation_id},
                }
            ],
        )
    else:
        return observation


@router.get("", summary="Get all observations")
@specify_observation_class(observation_class=None)
def get_all_observations(
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[ObservationResponse]:
    return get_observations(
        session=session,
        thing_id=thing_id,
        sensor_id=sensor_id,
        sample_id=sample_id,
        start_time=start_time,
        end_time=end_time,
        sort=sort,
        order=order,
        filter_=filter_,
    )


@router.get("/{observation_id}", summary="Get an observation by its ID")
def get_observation_by_id(
    session: session_dependency, observation_id: int
) -> ObservationResponse:
    return simple_get_by_id(session, Observation, observation_id)


# ============= EOF =============================================
