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
from fastapi import APIRouter, Depends
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from db import adder
from db.engine import get_db_session
from db.observation.geothermal import GeothermalObservation
from db.observation.groundwaterlevel import GroundwaterLevelObservation
from db.observation.observation import Observation
from schemas.create.observation import (
    CreateObservation,
    CreateGroundwaterLevelObservation,
    CreateGeothermalObservation,
    CreateGroundwaterLevelObservationDirect,
    CreateGeothermalObservationDirect,
)
from schemas.response.observation import (
    ObservationResponse,
    GroundwaterLevelObservationResponse,
    GeothermalObservationResponse,
)
from services.query_helper import paginated_all_getter

router = APIRouter(prefix="/observation", tags=["observation"])


def direct_adder(session: Session, model, data):
    obs = Observation(
        series_id=data.series_id,
        observation_timestamp=data.observation_timestamp,
    )
    obs.release_status = data.release_status
    session.add(obs)
    session.commit()
    session.refresh(obs)

    model_obj = model(
        **data.model_dump(
            exclude={"series_id", "observation_timestamp", "release_status"}
        )
    )
    model_obj.observation = obs
    session.add(model_obj)
    session.commit()
    session.refresh(model_obj)
    return model_obj


# ============= Post =============================================
@router.post("/", response_model=ObservationResponse, status_code=HTTP_201_CREATED)
def add_observation(
    obs_data: CreateObservation, session: Session = Depends(get_db_session)
):
    """
    Add a new observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    return adder(session, Observation, obs_data)


@router.post("/groundwater-level", status_code=HTTP_201_CREATED)
def add_groundwater_level_observation(
    obs_data: (
        CreateGroundwaterLevelObservation | CreateGroundwaterLevelObservationDirect
    ),
    session: Session = Depends(get_db_session),
):
    """
    Add a new groundwater observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    if isinstance(obs_data, CreateGroundwaterLevelObservationDirect):
        return direct_adder(session, GroundwaterLevelObservation, obs_data)
    else:

        return adder(session, GroundwaterLevelObservation, obs_data)


@router.post("/geothermal", status_code=HTTP_201_CREATED)
def add_geothermal_observation(
    obs_data: CreateGeothermalObservation | CreateGeothermalObservationDirect,
    session: Session = Depends(get_db_session),
):
    """
    Add a new geothermal observation to the database.
    This endpoint is currently a placeholder and does not implement any functionality.
    """
    if isinstance(obs_data, CreateGeothermalObservationDirect):
        return direct_adder(session, GeothermalObservation, obs_data)
    else:
        return adder(session, GeothermalObservation, obs_data)


# ============= Get ==============================================
@router.get("/", response_model=CustomPage[ObservationResponse])
def get_observations(
    series_id: int | None = None,
    session: Session = Depends(get_db_session),
):
    """
    Retrieve all observations from the database.
    """
    if series_id is not None:
        sql = select(Observation).where(Observation.series_id == series_id)
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, Observation)


@router.get(
    "/groundwater-level", response_model=CustomPage[GroundwaterLevelObservationResponse]
)
def get_groundwater_level_observations(
    series_id: int | None = None, session: Session = Depends(get_db_session)
):
    """
    Retrieve all groundwater level observations from the database.
    """
    if series_id is not None:
        sql = (
            select(GroundwaterLevelObservation)
            .join(Observation)
            .where(Observation.series_id == series_id)
        )
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, GroundwaterLevelObservation)


@router.get("/geothermal", response_model=CustomPage[GeothermalObservationResponse])
def get_groundwater_level_observations(
    series_id: int | None = None, session: Session = Depends(get_db_session)
):
    """
    Retrieve all groundwater level observations from the database.
    """
    if series_id is not None:
        sql = (
            select(GeothermalObservation)
            .join(Observation)
            .where(Observation.series_id == series_id)
        )
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, GeothermalObservation)


# ============= EOF =============================================
