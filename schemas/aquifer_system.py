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

    type: str
    coordinates: (
        List[float]
        | List[List[float]]
        | List[List[List[float]]]
        | List[List[List[List[float]]]]
    )


class AquiferSystemResponse(BaseResponseModel):
    """
    Response schema for aquifer system details.
    """

    name: str
    description: str | None = None
    primary_aquifer_type: str
    geographic_scale: str
    boundary: GeoJSONGeometry | None = None
