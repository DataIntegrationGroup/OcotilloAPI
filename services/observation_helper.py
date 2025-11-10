from datetime import datetime
from typing import List

from fastapi import Request, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND

from db import (
    Observation,
    Sample,
    FieldActivity,
    FieldEvent,
    Thing,
    TransducerObservation,
    Deployment,
    TransducerObservationBlock,
)
from schemas.observation import (
    ObservationResponse,
    WaterChemistryObservationResponse,
    GroundwaterLevelObservationResponse,
)
from services.exceptions_helper import PydanticStyleException
from services.query_helper import simple_get_by_id, order_sort_filter


def get_activity_type_from_request(request: Request) -> str:
    path = request.url.path
    path_components = path.split("/")
    if len(path_components) == 2:
        # no sample type specified in path
        activity_type_in_path = path_components[1]
    if len(path_components) >= 3:
        # sample type specified in path
        activity_type_in_path = path_components[2]

    activity_type = activity_type_in_path.replace("-", " ")
    return activity_type


def get_transducer_observations(
    session: Session,
    thing_id: int | None = None,
    parameter_id: int | None = None,
    sensor_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str = Query(alias="filter", default=None),
):
    # Subquery to get latest block for each observation
    block_subq = (
        select(TransducerObservationBlock.id)
        .where(
            TransducerObservationBlock.parameter_id
            == TransducerObservation.parameter_id,
            TransducerObservationBlock.start_datetime
            <= TransducerObservation.observation_datetime,
            TransducerObservationBlock.end_datetime
            >= TransducerObservation.observation_datetime,
        )
        .order_by(desc(TransducerObservationBlock.start_datetime))
        .limit(1)
        .correlate(TransducerObservation)
        .scalar_subquery()
    )

    query = (
        select(TransducerObservation, TransducerObservationBlock)
        .join(Deployment, TransducerObservation.deployment_id == Deployment.id)
        .join(TransducerObservationBlock, TransducerObservationBlock.id == block_subq)
    )

    if start_time:
        query = query.where(TransducerObservation.observation_datetime >= start_time)
    if end_time:
        query = query.where(TransducerObservation.observation_datetime <= end_time)

    if parameter_id:
        query = query.where(TransducerObservation.parameter_id == parameter_id)
    if thing_id:
        query = query.where(Deployment.thing_id == thing_id)

    def transformer(result):
        from schemas.transducer import (
            TransducerObservationWithBlockResponse,
            TransducerObservationResponse,
            TransducerObservationBlockResponse,
        )

        return [
            TransducerObservationWithBlockResponse(
                observation=TransducerObservationResponse.model_validate(observation),
                block=TransducerObservationBlockResponse.model_validate(block),
            ).model_dump()
            for observation, block in result
        ]

    query = query.order_by(TransducerObservation.observation_datetime.desc())

    return paginate(query=query, conn=session, transformer=transformer)


def get_observations(
    request: Request,
    session: Session,
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
    | List[GroundwaterLevelObservationResponse]
):
    """
    Retrieve all observations
    """
    activity_type_is_retrievable = False
    activity_type = get_activity_type_from_request(request)

    sql = select(Observation)
    if thing_id is not None:
        activity_type_is_retrievable = True
        sql = sql.join(Sample, Sample.id == Observation.sample_id)
        sql = sql.join(FieldActivity, FieldActivity.id == Sample.field_activity_id)
        sql = sql.join(FieldEvent, FieldEvent.id == FieldActivity.field_event_id)
        sql = sql.join(Thing, Thing.id == FieldEvent.thing_id)
        sql = sql.where(Thing.id == thing_id)
    if sample_id is not None:
        sql = sql.where(Observation.sample_id == sample_id)
    if sensor_id is not None:
        sql = sql.where(Observation.sensor_id == sensor_id)

    if start_time:
        sql = sql.where(Observation.observation_datetime >= start_time)
    if end_time:
        sql = sql.where(Observation.observation_datetime <= end_time)

    # root of path is /observation
    if activity_type != "observation":
        if activity_type_is_retrievable is False:
            sql = sql.join(Sample, Sample.id == Observation.sample_id)
            sql = sql.join(FieldActivity, FieldActivity.id == Sample.field_activity_id)
        sql = sql.where(FieldActivity.activity_type == activity_type)

    sql = order_sort_filter(sql, Observation, sort, order, filter_)

    if not order:
        sql = sql.order_by(Observation.observation_datetime.desc())

    return paginate(query=sql, conn=session)


def verify_observed_property_corresponds_with_activity_type(
    observation: Observation, request: Request
):
    """
    Developer's notes & TODO

    This is only used when getting one observation by its ID, and when patching
    a single observation. Since it uses lazy loads that shouldn't be much of an
    issue, but if we notice performance problems getting the single record
    should use joinedloads so everything is done in a single database query.
    """
    requested_activity_type = get_activity_type_from_request(request)
    actual_activity_type = observation.sample.field_activity.activity_type

    if actual_activity_type != requested_activity_type:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "type": "value_error",
                    "input": {"observation_id": observation.id},
                    "msg": f"Observation with ID {observation.id} is not a {requested_activity_type} observation. It is a {actual_activity_type} observation.",
                }
            ],
        )


def get_observation_of_an_activity_type_by_id(
    session: Session, request: Request, observation_id: int
) -> Observation:
    """
    Retrieve an observation by its ID.
    """
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_activity_type(observation, request)

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

    verify_observed_property_corresponds_with_activity_type(observation, request)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(observation, key, value)

    if user:
        observation.updated_by_id = user["sub"]
        observation.updated_by_name = user["name"]

    session.commit()
    session.refresh(observation)
    return observation
