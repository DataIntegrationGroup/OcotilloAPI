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

from pydantic import BaseModel, model_validator, PastDate

from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel
from schemas.location import LocationResponse

from datetime import date


# -------- CREATE ----------
class CreateThingIdLink(BaseModel):
    """
    Schema for creating a link between a thing and its ID.
    """

    thing_id: int
    relation: str
    alternate_id: str
    alternate_organization: str


class CreateBaseThing(BaseCreateModel):
    """
    Developer's notes

    thing_type does not need to be set by the user, this is determined by the
    POST endpoint

    e.g. POST /thing/water-well, POST /thing/spring determines the thing_type
    """

    location_id: int | None = None  # Optional location ID for the thing
    group_id: int | None = None  # Optional group ID for the thing
    name: str  # Name of the thing
    first_visit_date: PastDate | None = None  # Date of NMBGMR's first visit


class CreateWell(CreateBaseThing):
    """
    Schema for creating a well.
    """

    well_purpose: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None


class CreateSpring(CreateBaseThing):
    """
    Schema for creating a spring.
    """

    spring_type: str | None = None


class CreateWellScreen(BaseCreateModel):
    """
    Schema for creating a well screen.
    """

    thing_id: int
    screen_depth_bottom: float
    screen_depth_top: float
    screen_type: str | None = None
    screen_description: str | None = None

    # validate that screen depth bottom is greater than top
    @model_validator(mode="after")
    def check_depths(self):
        if self.screen_depth_bottom < self.screen_depth_top:
            raise ValueError(
                "screen_depth_bottom must be greater than screen_depth_top"
            )
        return self


# ------ RESPONSE ----------
class BaseThingResponse(BaseResponseModel):
    name: str
    thing_type: str
    active_location: LocationResponse | None = None
    first_visit_date: date | None = None


class WellResponse(BaseThingResponse):
    """
    Response schema for well details.
    """

    # api_id: str | None = None
    # ose_pod_id: str | None = None
    # usgs_id: str | None = None

    well_purpose: str | None = None  # e.g., "Production", "Observation", etc.
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None
    # Additional fields can be added as needed


class SpringResponse(BaseThingResponse):
    """
    Response schema for spring details.
    """

    spring_type: str | None = None  # e.g., "Natural", "Artifical", etc.


class ThingResponse(WellResponse, SpringResponse):
    pass


class ThingIdLinkResponse(BaseResponseModel):
    thing_id: int
    thing: ThingResponse
    relation: str
    alternate_id: str
    alternate_organization: str


class LocationWellResponse(LocationResponse):
    """
    Response schema for sample location with well details.
    """

    well: List[WellResponse] = []  # List of wells associated with the sample location


class WellScreenResponse(BaseResponseModel):
    """
    Response schema for well screen details.
    """

    thing_id: int
    thing: WellResponse
    screen_depth_bottom: float
    screen_depth_top: float
    screen_type: str | None = None
    screen_description: str | None = None


class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str
    coordinates: (
        List[float]
        | List[List[float]]
        | List[List[List[float]]]
        | List[List[List[List[float]]]]
    )  # Supports Point, LineString, Polygon, MultiPolygon


class Feature(BaseModel):
    """
    Feature schema for GeoJSON response.
    """

    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: dict = {}


class FeatureCollectionResponse(BaseModel):
    """
    Response schema for GeoJSON FeatureCollection.
    """

    type: str = "FeatureCollection"
    features: List[Feature] = []


# -------- UPDATE ------------
class UpdateThing(BaseUpdateModel):
    """
    Schema for updating a thing.
    """

    name: str | None = None  # Optional name for the thing
    first_visit_date: date | None = None  # Date of NMBGMR's first visit


class UpdateWell(UpdateThing):

    well_purpose: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None


class UpdateSpring(UpdateThing):
    spring_type: str | None = None


class UpdateThingIdLink(BaseUpdateModel):
    alternate_organization: str | None = None
    alternate_id: str | None = None
    relation: str | None = None


class UpdateWellScreen(BaseUpdateModel):
    screen_depth_bottom: float | None = None
    screen_depth_top: float | None = None
    screen_description: str | None = None
    screen_type: str | None = None


# ============= EOF =============================================
