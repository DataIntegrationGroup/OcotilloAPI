from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND

from db import Observation
from services.exceptions_helper import PydanticStyleException
from services.query_helper import simple_get_by_id


def verify_observed_property_corresponds_with_observation_class(
    observation: Observation, observation_class: str
):
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
    session: Session, observation_id: int, observation_class: str
) -> Observation:
    """
    Retrieve an observation by its ID.
    """
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_observation_class(
        observation, observation_class
    )

    return observation


def observation_model_patcher(
    session: Session,
    observation_id: int,
    payload: BaseModel,
    observation_class: str,
    user: dict,
) -> Observation:
    """
    Patch an observation model with the provided payload.
    """
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    observation = simple_get_by_id(session, Observation, observation_id)

    verify_observed_property_corresponds_with_observation_class(
        observation, observation_class
    )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(observation, key, value)

    if user:
        observation.updated_by_id = user["sub"]
        observation.updated_by_name = user["name"]

    session.commit()
    session.refresh(observation)
    return observation
