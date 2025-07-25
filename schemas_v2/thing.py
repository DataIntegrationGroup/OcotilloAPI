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
from datetime import datetime
from typing import List

from pydantic import BaseModel, model_validator

from schemas import ORMBaseModel
from schemas_v2.location import LocationResponse


# -------- CREATE ----------
class CreateThingIdLink(BaseModel):
    """
    Schema for creating a link between a thing and its ID.
    """

    thing_id: int
    relation: str
    alternate_id: str
    alternate_organization: str


class CreateBaseThing(BaseModel):
    location_id: int | None = None  # Optional location ID for the thing
    name: str  # Name of the thing
    group: str | None = None  # Optional group ID for the thing
    thing_type: str | None = None  # Type of the thing (e.g., "Well", "Spring", etc.)


class CreateWell(CreateBaseThing):
    """
    Schema for creating a well.
    """

    # api_id: str | None = None
    # ose_pod_id: str | None = None
    well_type: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None


class CreateSpring(CreateBaseThing):
    """
    Schema for creating a spring.
    """

    spring_type: str | None = None


class CreateThing(CreateWell, CreateSpring):
    """
    Schema for creating a thing.
    """


class CreateWellScreen(BaseModel):
    """
    Schema for creating a well screen.
    """

    thing_id: int
    screen_depth_bottom: float
    screen_depth_top: float
    screen_type: str | None = None

    @model_validator(mode="after")
    def validate_screen_type(self):
        if self.screen_type is not None:
            valid_screen_types = [
                "PVC",
            ]  # todo: get valid screen types from database
            if self.screen_type not in valid_screen_types:
                raise ValueError(
                    f"Invalid screen_type: {self.screen_type}. "
                    f"Valid options are: {', '.join(valid_screen_types)}."
                )
        return self

    # validate that screen depth bottom is greater than top
    @model_validator(mode="after")
    def check_depths(self):
        if self.screen_depth_bottom < self.screen_depth_top:
            raise ValueError(
                "screen_depth_bottom must be greater than screen_depth_top"
            )
        return self


# ------ RESPONSE ----------
class BaseThingResponse(ORMBaseModel):
    name: str
    thing_type: str
    id: int


class WellResponse(BaseThingResponse):
    """
    Response schema for well details.
    """

    # api_id: str | None = None
    # ose_pod_id: str | None = None
    # usgs_id: str | None = None

    well_type: str | None = None  # e.g., "Production", "Observation", etc.
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


class LocationWellResponse(LocationResponse):
    """
    Response schema for sample location with well details.
    """

    well: List[WellResponse] = []  # List of wells associated with the sample location


class WellScreenResponse(ORMBaseModel):
    """
    Response schema for well screen details.
    """

    thing_id: int
    screen_depth_bottom: float
    screen_depth_top: float


class GroupResponse(ORMBaseModel):
    """
    Response schema for group details.
    """

    name: str
    description: str | None = None


class GeoJSONGeometry(BaseModel):
    """
    Geometry schema for GeoJSON response.
    """

    type: str
    coordinates: (
        List[float] | List[List[float]] | List[List[List[float]]]
    )  # Supports Point, LineString, Polygon, etc.


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
class UpdateThing(BaseModel):
    """
    Schema for updating a thing.
    """

    # location_id: int | None = None  # Optional location ID for the thing
    name: str | None = None  # Optional name for the thing
    # group: str | None = None  # Optional group for the thing
    # description: str | None = None  # Optional description of the thing
    # tags: list[str] | None = None  # Optional tags associated with the thing


class UpdateWell(BaseModel):
    # location_id: int | None = None  # Optional location ID for the well
    # name: str | None = None  # Optional name for the well
    # api_id: str | None = None
    # ose_pod_id: str | None = None
    well_type: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    well_construction_notes: str | None = None

    # group: str | None = None  # Optional group for the well


# ============= EOF =============================================
