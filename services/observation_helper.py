from pydantic import BaseModel
from sqlalchemy.orm import Session, DeclarativeBase
from starlette.status import HTTP_404_NOT_FOUND

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


def observation_model_patcher(
    session: Session,
    model: DeclarativeBase,
    item_id: int,
    payload: BaseModel,
    observation_class: str,
    user: dict,
) -> object:
    """
    Patch an observation model with the provided payload.
    """
    # simple_get_by_id raises HTTP_404_NOT_FOUND if the item is not found
    item = simple_get_by_id(session, model, item_id)

    observed_property = item.observed_property

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
                    "input": {"observation_id": item_id},
                    "msg": f"{observation_class.capitalize()} observation with ID {item_id} not found. It is a {actual_observation_class} observation.",
                }
            ],
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    if user:
        item.updated_by_id = user["sub"]
        item.updated_by_name = user["name"]

    session.commit()
    session.refresh(item)
    return item
