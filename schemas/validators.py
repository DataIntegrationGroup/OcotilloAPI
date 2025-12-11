"""
schemas/validators.py
Reusable Pydantic validators and mixins for aquifer and geology related schemas.
May consider expansion for other domain models in the future.
"""

from pydantic import model_validator, field_validator, BaseModel, Field

from services.validation.geospatial import validate_wkt_geometry


class DepthIntervalMixin(BaseModel):
    """
    Mixin to enforce:
    1. Depths are non-negative (via Field constraints).
    2. Bottom depth > top depth (via model_validator).
    Assumes the model has 'top_depth' and 'bottom_depth' fields.
    """

    top_depth: float = Field(ge=0)
    bottom_depth: float = Field(ge=0)

    @model_validator(mode="after")
    def check_depth_logical_order(self) -> "DepthIntervalMixin":
        if self.bottom_depth <= self.top_depth:
            raise ValueError(
                f"Bottom depth ({self.bottom_depth}) must be greater "
                f"than top depth ({self.top_depth})"
            )
        return self


class GeometryMixin(BaseModel):
    """
    Mixin to validate WKT strings for boundary fields.
    Delegates logic to the validate_wkt_geometry service function.
    """

    boundary: str | None = None

    @field_validator("boundary")
    @classmethod
    def validate_wkt(cls, v: str | None) -> str | None:
        return validate_wkt_geometry(v)
