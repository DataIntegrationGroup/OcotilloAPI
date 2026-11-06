from pydantic import Field

from core.enums import Lithology
from schemas import BaseResponseModel
from schemas.geologic_formation import GeologicFormationGeoJSONResponse
from schemas.validators import DepthIntervalMixin


# ------ CREATE ----------
class CreateStratigraphicInterval(DepthIntervalMixin):
    """
    Schema for one depth interval in a well's stratigraphic log.
    Uses DepthIntervalMixin to enforce bottom_depth > top_depth.
    """

    thing_id: int
    geologic_formation_id: int | None = None
    top_depth: float = Field(ge=0)
    bottom_depth: float = Field(ge=0)
    lithology: Lithology | None = None
    lithologic_modifier: str | None = None
    contributing_unit: bool | None = None
    source: str | None = None


# ------ RESPONSE ----------
class StratigraphicIntervalResponse(BaseResponseModel):
    """Response schema for one depth interval in a well's stratigraphic log."""

    thing_id: int
    geologic_formation_id: int | None = None
    geologic_formation: GeologicFormationGeoJSONResponse | None = None
    top_depth: float
    top_depth_unit: str = "ft"
    bottom_depth: float
    bottom_depth_unit: str = "ft"
    lithology: str | None = None
    lithologic_modifier: str | None = None
    contributing_unit: bool | None = None
    source: str | None = None
