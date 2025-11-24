from typing import List

from pydantic import BaseModel

from schemas import BaseResponseModel


# ------ CREATE ----------
class CreateAquiferSystem(BaseModel):
    """
    Schema for creating an aquifer system.
    Used during data transfer and API creation.
    """

    name: str
    description: str | None = None
    primary_aquifer_type: str
    geographic_scale: str
    boundary: str | None = None


# ------ RESPONSE ----------
class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str = "MULTIPOLYGON"
    coordinates: List[List[List[float]]]


class GeoJSONProperties(BaseResponseModel):
    """
    Response schema for aquifer system details.
    """

    name: str
    description: str | None = None
    primary_aquifer_type: str
    geographic_scale: str


class AquiferSystemGeoJSONResponse(BaseModel):
    """
    Response schema for aquifer system details.
    """

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties
