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
from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, field_validator

from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel
from services.validation.geospatial import validate_wkt_geometry

"""
TODO

Create common validator classes to be shared amongst create and update schemas.
Since many fields are optional in the update schemas set check_fields=False in the field_validator.
"""


# -------- CREATE ----------
class CreateLocation(BaseCreateModel):
    """
    Schema for creating a sample location.
    """

    name: str | None = None
    notes: str | None = None
    point: str  # point is required and should be in WKT format
    release_status: str | None = "draft"
    elevation_accuracy: float | None = None
    elevation_method: str | None = None
    coordinate_accuracy: float | None = None
    coordinate_accuracy_unit: str | None = None
    coordinate_method: str | None = None

    @classmethod
    @field_validator("point")
    def validate_point_is_wkt(cls, wkt):
        return validate_wkt_geometry(wkt)


class CreateGroupThing(BaseModel):
    """
    Schema for creating a group location.
    """

    group_id: int
    thing_id: int


# -------- RESPONSE ----------
class LocationResponse(BaseResponseModel):
    """
    Response schema for sample location details.
    """

    name: str | None = None
    point: str
    release_status: str

    @field_validator("point", mode="before")
    def point_to_wkt(cls, value):
        if isinstance(value, WKBElement):
            return to_shape(value).wkt

        # If the value is a string, assume it's already in WKT format
        if isinstance(value, str):
            return value

        return None


class GroupLocationResponse(BaseResponseModel):
    """
    Response schema for group location details.
    """

    group_id: int
    location_id: int


# -------- UPDATE ----------
class UpdateLocation(BaseUpdateModel):
    """
    Schema for updating a location.
    """

    name: str | None = None
    notes: str | None = None
    point: str | None = None


# ============= EOF =============================================
