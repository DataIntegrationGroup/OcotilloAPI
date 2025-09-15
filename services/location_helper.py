from shapely.wkt import loads
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.location import Location
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)


def set_geographic_attributes(
    session: Session, payload: BaseModel, location: Location
) -> None:
    """
    Set geographic attributes for a location based off of the point. This function
    is to be used for both POST and PATCH requests.
    """
    if payload.point is not None:
        point = loads(payload.point)
        longitude = point.x
        latitude = point.y
        location.state = get_state_from_point(longitude, latitude)
        location.county = get_county_from_point(longitude, latitude)
        location.quad_name = get_quad_name_from_point(longitude, latitude)
        session.commit()
