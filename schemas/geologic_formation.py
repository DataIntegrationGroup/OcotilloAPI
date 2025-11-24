from typing import List

from pydantic import BaseModel

from schemas import BaseResponseModel


# ------ RESPONSE ----------
class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str = "MULTIPOLYGON"
    coordinates: List[List[List[float]]]


class GeoJSONProperties(BaseResponseModel):
    """
    Response schema for geologic formation details.
    """

    formation_code: str | None = None
    description: str | None = None
    lithology: str | None = None


class GeologicFormationGeoJSONResponse(BaseModel):
    """
    Response schema for geologic formation details.
    """

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties


class ThingGeologicFormationAssociationResponse(BaseResponseModel):
    """
    Response schema for the association between a Thing and a GeologicFormation.
    Includes depth interval information.
    """

    thing_id: int
    geologic_formation_id: int | None = None
    geologic_formation: GeologicFormationGeoJSONResponse | None = None
    top_depth: float
    top_depth_unit: str = "ft"
    bottom_depth: float
    bottom_depth_unit: str = "ft"
