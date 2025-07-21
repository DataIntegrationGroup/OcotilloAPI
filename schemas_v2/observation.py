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

from pydantic import BaseModel


class GroundwaterLevelMixin:
    depth_to_water: float
    measuring_point_height: float


class GeothermalMixin:
    depth: float
    temperature: float


class ChildObservationModel(BaseModel):
    observation_id: int
    observation_timestamp: datetime


# -------- CREATE ----------
class CreateObservation(BaseModel):
    series_id: int
    release_status: str
    observation_timestamp: datetime


class CreateGroundwaterLevelObservation(ChildObservationModel, GroundwaterLevelMixin):
    pass


class CreateGeothermalObservation(ChildObservationModel, GeothermalMixin):
    pass


class CreateGroundwaterLevelObservationDirect(CreateObservation, GroundwaterLevelMixin):
    pass


class CreateGeothermalObservationDirect(CreateObservation, GeothermalMixin):
    pass


# -------- RESPONSE ----------
class ObservationResponse(BaseModel):
    id: int
    observation_timestamp: datetime


class GroundwaterLevelObservationResponse(BaseModel):
    observation_id: int
    observation_timestamp: datetime

    depth_to_water: float


class GeothermalObservationResponse(BaseModel):
    observation_id: int
    observation_timestamp: datetime

    temperature: float
    depth: float


# -------- UPDATE ----------
# ============= EOF =============================================
