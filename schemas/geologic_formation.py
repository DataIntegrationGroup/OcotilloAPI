from typing import List

from pydantic import BaseModel

from schemas import BaseResponseModel


# ------ RESPONSE ----------
class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str
    coordinates: (
        List[float]
        | List[List[float]]
        | List[List[List[float]]]
        | List[List[List[List[float]]]]
    )


class GeologicFormationResponse(BaseResponseModel):
    """
    Response schema for geologic formation details.
    """

    formation_code: str | None = None
    description: str | None = None
    lithology: str | None = None
    boundary: GeoJSONGeometry | None = None


class ThingGeologicFormationAssociationResponse(BaseResponseModel):
    """
    Response schema for the association between a Thing and a GeologicFormation.
    Includes depth interval information.
    """

    thing_id: int
    geologic_formation_id: int | None = None
    geologic_formation: GeologicFormationResponse | None = None
    top_depth: float
    top_depth_unit: str = "ft"
    bottom_depth: float
    bottom_depth_unit: str = "ft"
