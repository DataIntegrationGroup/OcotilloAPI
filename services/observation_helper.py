from datetime import datetime
import logging
import time
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
from services.env import get_bool_env
from services.query_helper import simple_get_by_id, order_sort_filter

logger = logging.getLogger(__name__)


def is_debug_timing_enabled() -> bool:
    return bool(get_bool_env("API_DEBUG_TIMING", False))


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
    deployment_rows: list[tuple[int, int]] = []
    deployment_to_thing: dict[int, int] = {}

    if thing_id:
        item = session.get(Thing, thing_id)
        if item is None:
            empty_query = select(TransducerObservation).where(False)
            return paginate(query=empty_query, conn=session)
        deployment_rows = session.execute(
            select(Deployment.id, Deployment.thing_id).where(
                Deployment.thing_id == thing_id
            )
        ).all()
        deployment_to_thing = {
            deployment_id: deployment_thing_id
            for deployment_id, deployment_thing_id in deployment_rows
        }

    query = select(TransducerObservation)

    if start_time:
        query = query.where(TransducerObservation.observation_datetime >= start_time)
    if end_time:
        query = query.where(TransducerObservation.observation_datetime <= end_time)

    if parameter_id:
        query = query.where(TransducerObservation.parameter_id == parameter_id)
    if thing_id:
        deployment_ids = list(deployment_to_thing)
        if not deployment_ids:
            empty_query = select(TransducerObservation).where(False)
            return paginate(query=empty_query, conn=session)
        query = query.where(TransducerObservation.deployment_id.in_(deployment_ids))

    def transformer(observations):
        from schemas.transducer import (
            TransducerObservationWithBlockResponse,
            TransducerObservationResponse,
            TransducerObservationBlockResponse,
        )

        if not observations:
            return []

        deployment_ids = {observation.deployment_id for observation in observations}
        if not deployment_to_thing or not deployment_ids.issubset(deployment_to_thing):
            deployment_rows = session.execute(
                select(Deployment.id, Deployment.thing_id).where(
                    Deployment.id.in_(deployment_ids)
                )
            ).all()
            deployment_to_thing.update(
                {
                    deployment_id: deployment_thing_id
                    for deployment_id, deployment_thing_id in deployment_rows
                }
            )

        thing_ids = {
            deployment_to_thing[observation.deployment_id]
            for observation in observations
            if observation.deployment_id in deployment_to_thing
        }
        parameter_ids = {observation.parameter_id for observation in observations}
        observation_datetimes = [
            observation.observation_datetime for observation in observations
        ]

        block_rows = session.scalars(
            select(TransducerObservationBlock)
            .where(
                TransducerObservationBlock.thing_id.in_(thing_ids),
                TransducerObservationBlock.parameter_id.in_(parameter_ids),
                TransducerObservationBlock.start_datetime <= max(observation_datetimes),
                TransducerObservationBlock.end_datetime >= min(observation_datetimes),
            )
            .order_by(
                TransducerObservationBlock.thing_id,
                TransducerObservationBlock.parameter_id,
                desc(TransducerObservationBlock.start_datetime),
            )
        ).all()

        block_map: dict[tuple[int, int], list[TransducerObservationBlock]] = {}
        for block in block_rows:
            key = (block.thing_id, block.parameter_id)
            if key not in block_map:
                block_map[key] = []
            block_map[key].append(block)

        response_items = []
        for observation in observations:
            thing_id_for_observation = deployment_to_thing.get(
                observation.deployment_id
            )
            if thing_id_for_observation is None:
                continue

            matching_block = next(
                (
                    block
                    for block in block_map.get(
                        (thing_id_for_observation, observation.parameter_id), []
                    )
                    if block.start_datetime
                    <= observation.observation_datetime
                    <= block.end_datetime
                ),
                None,
            )
            if matching_block is None:
                continue

            response_items.append(
                TransducerObservationWithBlockResponse(
                    observation=TransducerObservationResponse.model_validate(
                        observation
                    ),
                    block=TransducerObservationBlockResponse.model_validate(
                        matching_block
                    ),
                ).model_dump()
            )

        return response_items

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

    started_at = time.perf_counter()
    page = paginate(query=sql, conn=session)
    if is_debug_timing_enabled():
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "observation query completed path=%s thing_id=%s sensor_id=%s sample_id=%s duration_ms=%s",
            request.url.path,
            thing_id,
            sensor_id,
            sample_id,
            duration_ms,
            extra={
                "event": "observation_query_completed",
                "path": request.url.path,
                "thing_id": thing_id,
                "sensor_id": sensor_id,
                "sample_id": sample_id,
                "duration_ms": duration_ms,
            },
        )
    return page


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

    if isinstance(user, dict):
        observation.updated_by_id = user["sub"]
        observation.updated_by_name = user["name"]

    session.commit()
    session.refresh(observation)
    return observation
