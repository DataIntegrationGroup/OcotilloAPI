# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from datetime import datetime, timezone

from pydantic import (
    BaseModel,
    ConfigDict,
    AwareDatetime,
    field_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

from core.enums import ReleaseStatus

DT_FMT = "%Y-%m-%dT%H:%M:%SZ"


class ResourceNotFoundResponse(BaseModel):
    detail: str


class BaseCreateModel(BaseModel):
    release_status: ReleaseStatus = "draft"

    @field_validator("release_status", mode="before")
    @classmethod
    def coerce_release_status(cls, v):
        if isinstance(v, str):
            try:
                return ReleaseStatus(v)
            except ValueError:
                raise ValueError(f"Invalid release_status: {v}")
        return v


class BaseUpdateModel(BaseCreateModel):
    release_status: ReleaseStatus | None = None


# Custom type for UTC datetime serialization
class UTCAwareDatetime(AwareDatetime):
    """Custom datetime type that always serializes to UTC with 'Z' suffix."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler
    ) -> core_schema.CoreSchema:
        def serialize_dt(value: datetime) -> str:
            """Serialize datetime to UTC format with Z suffix."""
            if value is None:
                return None
            # Convert to UTC if not already
            if value.tzinfo != timezone.utc:
                value = value.astimezone(timezone.utc)
            # Format with Z suffix
            return value.strftime(DT_FMT)

        # Use generate_schema instead of calling handler directly
        python_schema = handler.generate_schema(datetime)
        return core_schema.no_info_after_validator_function(
            lambda x: x,
            python_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize_dt,
                return_schema=core_schema.str_schema(),
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler
    ) -> JsonSchemaValue:
        return handler(core_schema)


class BaseResponseModel(BaseModel):
    id: int  # every ORM model should have an id field
    created_at: UTCAwareDatetime
    release_status: ReleaseStatus

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# TODO: write function to convert any datetime field to UTC for use throughout
#       for schema field_validators
# e.g.
# def convert_datetime_field_to_utc(dt_field):
#   ...
#
# @field_validator("dt_field_name")
# def convert_to_utc(dt_field_name):
#   return convert_datetime_field_to_utc(dt_field_name)

# ============= EOF =============================================
