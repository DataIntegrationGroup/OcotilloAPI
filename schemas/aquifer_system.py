from typing import List

from pydantic import BaseModel, field_validator

from schemas import BaseResponseModel
from schemas.validators import GeometryMixin, validate_enum_input
from core.enums import AquiferType, GeographicScale  # Import specific Enums


# ------ CREATE ----------
class CreateAquiferSystem(BaseModel, GeometryMixin):
    """
    Schema for creating an aquifer system.
    Used during data transfer and API creation.
    """

    name: str
    description: str | None = None
    primary_aquifer_type: str
    geographic_scale: str
    # boundary field inherited from GeometryMixin

    @field_validator("primary_aquifer_type", mode="before")
    @classmethod
    def check_aquifer_type(cls, v):
        return validate_enum_input(v, AquiferType)

    @field_validator("geographic_scale", mode="before")
    @classmethod
    def check_geographic_scale(cls, v):
        return validate_enum_input(v, GeographicScale)


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
