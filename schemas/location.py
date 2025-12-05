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
from datetime import date
from typing import List, Any

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, model_validator, field_validator, Field, ConfigDict

from constants import SRID_WGS84, SRID_UTM_ZONE_13N
from core.enums import ElevationMethod, CoordinateMethod
from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel
from schemas.notes import NoteResponse, CreateNote, UpdateNote
from services.util import convert_m_to_ft, transform_srid
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
    # elevation_accuracy: float | None = None
    # elevation_method: ElevationMethod | None = None
    # coordinate_accuracy: float | None = None
    # coordinate_method: CoordinateMethod | None = None


class CreateGroupThing(BaseModel):
    """
    Schema for creating a group location.
    """

    group_id: int
    thing_id: int


# -------- RESPONSE ----------


class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: list = Field(
        max_length=3,
        min_length=3,
        description="Coordinates in [longitude, latitude, elevation] format",
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class GeoJSONUTMCoordinates(BaseModel):
    easting: float
    northing: float
    utm_zone: str = "13N"
    horizontal_datum: str = "NAD83"

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class GeoJSONProperties(BaseModel):
    elevation: float
    elevation_unit: str = "ft"
    vertical_datum: str = "NAVD88"
    elevation_method: ElevationMethod | None
    utm_coordinates: GeoJSONUTMCoordinates = Field(
        default_factory=GeoJSONUTMCoordinates
    )
    notes: list[NoteResponse] = []
    # AMPAPI date fields (read-only, populated only during migration)
    nma_date_created: date | None = None
    nma_site_date: date | None = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class LocationGeoJSONResponse(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: GeoJSONProperties

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @model_validator(mode="before")
    @classmethod
    def populate_fields(cls, data: Any) -> Any:
        # convert row to dictionary
        if not isinstance(data, dict):
            data_dict = {c.name: getattr(data, c.name) for c in data.__table__.columns}

            # @property and @declared_attr need to be added manually
            data_dict["elevation_method"] = data.elevation_method
            data_dict["notes"] = data.notes

        # add empty fields as necessary
        data_dict["geometry"] = {}
        data_dict["properties"] = {}
        data_dict["properties"]["utm_coordinates"] = {}

        # populate coordinates
        point_wgs84_wkb = data_dict.get("point")
        point_wgs84_wkt = to_shape(point_wgs84_wkb)
        elevation_m = data_dict.get("elevation")
        coordinates = [point_wgs84_wkt.x, point_wgs84_wkt.y, elevation_m]
        data_dict["geometry"]["coordinates"] = coordinates

        # populate properties
        data_dict["properties"]["notes"] = data_dict.get("notes")
        data_dict["properties"]["elevation"] = convert_m_to_ft(elevation_m)
        data_dict["properties"]["elevation_method"] = data_dict.get("elevation_method")
        # populate AMPAPI date fields
        data_dict["properties"]["nma_date_created"] = data_dict.get("nma_date_created")
        data_dict["properties"]["nma_site_date"] = data_dict.get("nma_site_date")

        # populate UTM coordinates
        point_utm_zone_13n_wkt = transform_srid(
            point_wgs84_wkt, SRID_WGS84, SRID_UTM_ZONE_13N
        )
        data_dict["properties"]["utm_coordinates"]["easting"] = point_utm_zone_13n_wkt.x
        data_dict["properties"]["utm_coordinates"][
            "northing"
        ] = point_utm_zone_13n_wkt.y

        return data_dict


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
    elevation_method: ElevationMethod | None
    state: str | None
    county: str | None
    quad_name: str | None

    # AMPAPI date fields (read-only, populated only during migration, not in Create/Update schemas)
    nma_date_created: date | None = None
    nma_site_date: date | None = None

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
