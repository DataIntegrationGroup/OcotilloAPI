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

from pydantic import BaseModel

from schemas import ORMBaseModel
from schemas.response.location import LocationResponse


class ThingResponse(ORMBaseModel):
    name: str


class SpringResponse(ORMBaseModel):
    pass


class WellResponse(ORMBaseModel):
    """
    Response schema for well details.
    """

    # api_id: str | None = None
    # ose_pod_id: str | None = None
    # usgs_id: str | None = None
    well_type: str | None = None
    well_depth: float | None = None  # in feet
    hole_depth: float | None = None  # in feet
    construction_notes: str | None = None
    # Additional fields can be added as needed


class LocationWellResponse(LocationResponse):
    """
    Response schema for sample location with well details.
    """

    well: List[WellResponse] = []  # List of wells associated with the sample location


class WellScreenResponse(ORMBaseModel):
    """
    Response schema for well screen details.
    """

    well_id: int
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


# ============= EOF =============================================
