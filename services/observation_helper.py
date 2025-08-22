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


def get_observation_class_from_request(request: Request) -> str:
    path = request.url.path
    path_components = path.split("/")
    if len(path_components) == 2:
        # no observation class specified in path
        observation_class_in_path = path_components[1]
    if len(path_components) >= 3:
        # observation class specified in path
        observation_class_in_path = path_components[2]

    observation_class = observation_class_in_path.replace("-", " ")
    return observation_class


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
    observation_class = get_observation_class_from_request(request)

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

    # root of path is /observation
    if observation_class != "observation":
        sql = sql.where(Observation.observed_property.like(f"{observation_class}:%"))

    sql = order_sort_filter(sql, Observation, sort, order, filter_)

    if not order:
        sql = sql.order_by(Observation.observation_datetime.desc())

    return paginate(query=sql, conn=session)


def verify_observed_property_corresponds_with_observation_class(
    observation: Observation, request: Request
):
    observation_class = get_observation_class_from_request(request)

    observed_property = observation.observed_property
    colon_index = observed_property.find(":")
    actual_observation_class = observed_property[:colon_index]

    if actual_observation_class != observation_class:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "type": "value_error",
                    "input": {"observation_id": observation.id},
                    "msg": f"Observation with ID {observation.id} is not a {observation_class} observation. It is a {actual_observation_class} observation.",
                }
            ],
        )


def get_observation_of_an_observation_class_by_id(
    session: Session, request: Request, observation_id: int
) -> Observation:
    """
    Retrieve an observation by its ID.
    """
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_observation_class(observation, request)

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

    verify_observed_property_corresponds_with_observation_class(observation, request)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(observation, key, value)

    if user:
        observation.updated_by_id = user["sub"]
        observation.updated_by_name = user["name"]

    session.commit()
    session.refresh(observation)
    return observation
