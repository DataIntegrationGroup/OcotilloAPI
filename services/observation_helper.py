from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND

from db import Observation
from services.exceptions_helper import PydanticStyleException
from services.query_helper import simple_get_by_id

observation_class_to_observed_properties = {
    "groundwater level": ["groundwater level"],
    "geothermal": ["temperature"],
    "water chemistry": ["pH", "Alkalinity as CaCO3"],
}

observation_property_to_class = {}
for key, value in observation_class_to_observed_properties.items():
    for prop in value:
        observation_property_to_class[prop] = key


def verify_observed_property_corresponds_with_observation_class(
    observation: Observation, observation_class: str
) -> None:
    """
    Verify that the observed property of the retrieved Observation corresponds
    with the observation class as defined by the path
    (e.g. /observation/water-chemistry). Raise an error if they do not
    correspond.
    """
    observed_property = observation.observed_property

    if (
        observed_property
        not in observation_class_to_observed_properties[observation_class]
    ):
        actual_observation_class = observation_property_to_class[observed_property]

        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "observation_id"],
                    "type": "value_error",
                    "input": {"observation_id": observation.id},
                    "msg": f"{observation_class.capitalize()} observation with ID {observation.id} not found. It is a {actual_observation_class} observation.",
                }
            ],
        )
    else:
        return True


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
