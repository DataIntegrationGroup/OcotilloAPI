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
from datetime import timezone
from pydantic import BaseModel, AwareDatetime, PastDatetime, field_validator
from typing import Annotated


# class GeothermalMixin:
#     depth: float
#     temperature: float


# -------- VALIDATE -------


class ValidateObservation(BaseModel):

    @field_validator("observation_timestamp", check_fields=False)
    def convert_observation_timestamp_to_utc(
        observation_timestamp: AwareDatetime,
    ) -> AwareDatetime:
        """
        Convert observation_timestamp to UTC timezone if it's not already. This runs after
        the Annotated validator PastDatetime() is run.
        """
        if (
            observation_timestamp is not None
            and observation_timestamp.tzinfo != timezone.utc
        ):
            return observation_timestamp.astimezone(timezone.utc)
        return observation_timestamp


# -------- CREATE ----------
class CreateBaseObservation(ValidateObservation):
    observation_timestamp: Annotated[AwareDatetime, PastDatetime()]
    sample_id: int
    sensor_id: int
    observed_property: str
    release_status: str


class CreateGroundwaterLevelObservation(CreateBaseObservation):
    depth_to_water: float
    measuring_point_height: float
    level_status: str


#
#
# class CreateGroundwaterLevelObservation(ChildObservationModel, GroundwaterLevelMixin):
#     pass
#
#
# class CreateGeothermalObservation(ChildObservationModel, GeothermalMixin):
#     pass
#
#
# class CreateGroundwaterLevelObservationDirect(CreateObservation, GroundwaterLevelMixin):
#     pass
#
#
# class CreateGeothermalObservationDirect(CreateObservation, GeothermalMixin):
#     pass


# -------- RESPONSE ----------
class BaseObservationResponse(BaseModel):
    id: int
    sample_id: int
    sensor_id: int
    observation_timestamp: AwareDatetime
    observed_property: str
    created_at: AwareDatetime
    release_status: str


class GroundwaterLevelObservationResponse(BaseObservationResponse):
    depth_to_water: float
    level_status: str


class GeothermalObservationResponse(BaseObservationResponse):

    temperature: float
    depth: float


class ObservationResponse(
    GroundwaterLevelObservationResponse, GeothermalObservationResponse
):
    """
    Response model for observations.
    Combines groundwater level and geothermal observation responses.
    """


# -------- UPDATE ----------
# ============= EOF =============================================
