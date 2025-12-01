"""
schemas/validators.py
Reusable Pydantic validators and mixins for aquifer and geology related schemas.
May consider expansion for other domain models in the future.
"""

from typing import Any, Type
from pydantic import model_validator, field_validator, BaseModel, ValueError

from enum import Enum


def validate_enum_input(v: Any, enum_cls: Type[Enum]) -> Any:
    """
    Validates that the input matches an enum value, either exactly or case-insensitively.
    Returns the actual Enum member value.
    """
    if v is None:
        return None

    # 1. Check if it's already a valid enum member or value
    try:
        return enum_cls(v).value
    except ValueError:
        pass

    # 2. Case-insensitive fallback (for string inputs)
    if isinstance(v, str):
        v_lower = v.lower()
        for member in enum_cls:
            if str(member.value).lower() == v_lower:
                return member.value

    # 3. Fail if no match found
    valid_options = [str(e.value) for e in enum_cls]
    raise ValueError(f"Invalid value '{v}'. Must be one of: {', '.join(valid_options)}")


class DepthIntervalMixin(BaseModel):
    """
    Mixin to enforce that bottom_depth is greater than top_depth.
    Assumes the model has 'top_depth' and 'bottom_depth' fields.
    """

    top_depth: float
    bottom_depth: float

    @model_validator(mode="after")
    def check_depth_logical_order(self) -> "DepthIntervalMixin":
        if self.bottom_depth is not None and self.top_depth is not None:
            if self.bottom_depth <= self.top_depth:
                raise ValueError(
                    f"Bottom depth ({self.bottom_depth}) must be greater "
                    f"than top depth ({self.top_depth})"
                )
        if self.top_depth < 0:
            raise ValueError("Top depth cannot be negative.")
        return self


class GeometryMixin(BaseModel):
    """
    Mixin to validate WKT strings for boundary fields.
    """

    boundary: str | None = None

    @field_validator("boundary")
    @classmethod
    def validate_wkt(cls, v: str | None) -> str | None:
        if v is None:
            return v

        # Basic String Check
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Boundary must be a valid WKT string.")
