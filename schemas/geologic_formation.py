from typing import List

from pydantic import BaseModel, field_validator, Field

from schemas import BaseResponseModel
from schemas.validators import DepthIntervalMixin, GeometryMixin
from core.enums import FormationCode, Lithology


# ------ CREATE ----------
class CreateGeologicFormation(BaseModel, GeometryMixin):
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


class CreateThingGeologicFormationAssociation(BaseModel, DepthIntervalMixin):
    """
    Schema for linking a Thing (Well) to a GeologicFormation.
    Uses DepthIntervalMixin to enforce bottom_depth > top_depth.
    """

    thing_id: int
    geologic_formation_id: int
    top_depth: float = Field(ge=0)
    bottom_depth: float = Field(ge=0)


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
