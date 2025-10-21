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

from pydantic import (
    BaseModel,
    ConfigDict,
    AwareDatetime,
    model_serializer,
    field_validator,
)

from core.enums import ReleaseStatus


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


class BaseResponseModel(BaseModel):
    id: int  # every ORM model should have an id field
    created_at: AwareDatetime
    release_status: ReleaseStatus

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @model_serializer
    def serialize(self):
        data = self.__dict__.copy()
        # If release_status is an enum, convert to string
        if hasattr(data.get("release_status"), "value"):
            data["release_status"] = data["release_status"].value
        return data


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
