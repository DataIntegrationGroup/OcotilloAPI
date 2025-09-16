from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from typing import List
from fastapi import Request, Query
from datetime import datetime

from core.dependencies import session_dependency
from db import Observation, Sample
from schemas.observation import (
    ObservationResponse,
    WaterChemistryObservationResponse,
    GeothermalObservationResponse,
    GroundwaterLevelObservationResponse,
)
from services.exceptions_helper import PydanticStyleException
from services.query_helper import simple_get_by_id, order_sort_filter


def get_sample_type_from_request(request: Request) -> str:
    path = request.url.path
    path_components = path.split("/")
    if len(path_components) == 2:
        # no sample type specified in path
        sample_type_in_path = path_components[1]
    if len(path_components) >= 3:
        # sample type specified in path
        sample_type_in_path = path_components[2]

    sample_type = sample_type_in_path.replace("-", " ")
    return sample_type


def get_observations(
    request: Request,
    session: session_dependency,
    thing_id: int | None = None,
    sensor_id: int | None = None,
    sample_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
) -> (
    List[ObservationResponse]
    | List[WaterChemistryObservationResponse]
    | List[GeothermalObservationResponse]
    | List[GroundwaterLevelObservationResponse]
):
    """
    Retrieve all observations
    """
    sample_table_is_joined = False
    sample_type = get_sample_type_from_request(request)

    sql = select(Observation)
    if thing_id is not None:
        sample_table_is_joined = True
        sql = sql.join(Sample, Sample.id == Observation.sample_id)
        sql = sql.where(Sample.thing_id == thing_id)
    if sample_id is not None:
        sql = sql.where(Observation.sample_id == sample_id)
    if sensor_id is not None:
        sql = sql.where(Observation.sensor_id == sensor_id)

    if start_time:
        sql = sql.where(Observation.observation_datetime >= start_time)
    if end_time:
        sql = sql.where(Observation.observation_datetime <= end_time)

    # root of path is /observation
    if sample_type != "observation":
        if sample_table_is_joined is False:
            sql = sql.join(Sample, Sample.id == Observation.sample_id)
        sql = sql.where(Sample.sample_type == sample_type)

    sql = order_sort_filter(sql, Observation, sort, order, filter_)

    if not order:
        sql = sql.order_by(Observation.observation_datetime.desc())

    return paginate(query=sql, conn=session)


def verify_observed_property_corresponds_with_sample_type(
    observation: Observation, request: Request
):
    requested_sample_type = get_sample_type_from_request(request)
    actual_sample_type = observation.sample.sample_type

    if actual_sample_type != requested_sample_type:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "type": "value_error",
                    "input": {"observation_id": observation.id},
                    "msg": f"Observation with ID {observation.id} is not a {requested_sample_type} observation. It is a {actual_sample_type} observation.",
                }
            ],
        )


def get_observation_of_a_sample_type_by_id(
    session: Session, request: Request, observation_id: int
) -> Observation:
    """
    Retrieve an observation by its ID.
    """
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_sample_type(observation, request)

    return observation


def observation_model_patcher(
    session: Session,
    request: Request,
    observation_id: int,
    payload: BaseModel,
    user: dict,
) -> Observation:
    """
    Patch an observation model with the provided payload.
    """
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_sample_type(observation, request)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(observation, key, value)

    if user:
        observation.updated_by_id = user["sub"]
        observation.updated_by_name = user["name"]

    session.commit()
    session.refresh(observation)
    return observation
