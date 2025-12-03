from typing import List

from pydantic import BaseModel
from schemas import BaseResponseModel
from schemas.validators import GeometryMixin
from core.enums import AquiferType, GeographicScale  # Import specific Enums


# ------ CREATE ----------
class CreateAquiferSystem(GeometryMixin):
    """
    Schema for creating an aquifer system.
    Used during data transfer and API creation.
    """

    name: str
    description: str | None = None
    primary_aquifer_type: AquiferType
    geographic_scale: GeographicScale | None = None
    # boundary field inherited from GeometryMixin


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
    primary_aquifer_type: AquiferType
    geographic_scale: GeographicScale | None


class AquiferSystemGeoJSONResponse(BaseModel):
    """
    Response schema for aquifer system details.
    """

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties
