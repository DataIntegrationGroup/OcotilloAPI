from typing import List

from pydantic import BaseModel, field_validator

from core.enums import FormationCode, Lithology
from schemas import BaseResponseModel
from schemas.validators import GeometryMixin


# ------ CREATE ----------
class CreateGeologicFormation(GeometryMixin):
    """
    Schema for creating a geologic formation.
    Used during data transfer and API creation.
    """

    # formation_code has its own custom uppercase validator
    formation_code: FormationCode | None = None
    description: str | None = None
    lithology: Lithology | None = None
    # boundary: inherited from GeometryMixin

    @field_validator("formation_code", mode="before")
    @classmethod
    def upper_case_code(cls, v: str | None) -> str | None:
        """
        Automatically uppercase the formation code.
        """
        if isinstance(v, str):
            return v.upper()
        return v


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
