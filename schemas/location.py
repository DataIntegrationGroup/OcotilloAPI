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
from typing import List

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, field_validator

from core.enums import ElevationMethod, CoordinateMethod
from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel
from schemas.notes import NoteResponse, CreateNote, UpdateNote
from services.validation.geospatial import validate_wkt_geometry


# -------- VALIDATE --------


class ValidateLocation(BaseModel):
    point: str

    @classmethod
    @field_validator("point", mode="before")
    def validate_point_is_wkt(cls, wkt):
        return validate_wkt_geometry(wkt)


# -------- CREATE ----------
class CreateLocation(BaseCreateModel, ValidateLocation):
    """
    Schema for creating a sample location.
    """

    # name: str | None = None
    # TODO: AI suggested managing notes via a separate /locations/{id}/notes endpoint.
    #  I don't know if we want to do that, but am leaving this comment for future reference.
    # notes: str | None = None
    notes: List[CreateNote] = []
    point: str  # point is required and should be in WKT format
    elevation: float
    elevation_accuracy: float | None = None
    elevation_method: ElevationMethod | None = None
    coordinate_accuracy: float | None = None
    coordinate_method: CoordinateMethod | None = None


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

    # name: str | None
    # The 'notes' field is now a List of NoteResponse objects,
    # matching the polymorphic relationship in the database model.
    notes: List[NoteResponse] = []
    point: str
    elevation: float | None
    horizontal_datum: str = "WGS84"
    vertical_datum: str = "NAVD88"
    elevation_accuracy: float | None
    elevation_method: ElevationMethod | None
    coordinate_accuracy: float | None
    coordinate_method: CoordinateMethod | None
    state: str | None
    county: str | None
    quad_name: str | None

    # The new relationship to the polymorphic Notes table
    notes: List[NoteResponse] = []

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
class UpdateLocation(BaseUpdateModel, ValidateLocation):
    """
    Schema for updating a location. Notes are managed via the polymorphic Notes table.
    """

    # name: str | None = None
    # TODO: AI suggested managing notes via a separate API endpoint, /notes/{note_id}.
    #  I don't know if we want to do that, but am leaving this comment for future reference.
    notes: List[UpdateNote] = []
    point: str | None = None
    elevation: float | None = None
    elevation_accuracy: float | None = None
    elevation_method: ElevationMethod | None = None
    coordinate_accuracy: float | None = None
    coordinate_method: CoordinateMethod | None = None


# ============= EOF =============================================
