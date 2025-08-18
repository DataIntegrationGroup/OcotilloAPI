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

    @field_validator("observation_datetime", check_fields=False)
    def convert_observation_datetime_to_utc(
        observation_datetime: AwareDatetime,
    ) -> AwareDatetime:
        """
        Convert observation_timestamp to UTC timezone if it's not already. This runs after
        the Annotated validator PastDatetime() is run.
        """
        if (
            observation_datetime is not None
            and observation_datetime.tzinfo != timezone.utc
        ):
            return observation_datetime.astimezone(timezone.utc)
        return observation_datetime


# -------- CREATE ----------
class CreateBaseObservation(ValidateObservation):
    observation_datetime: Annotated[AwareDatetime, PastDatetime()]
    sample_id: int | None = None
    field_sample_id: str | None = None
    sensor_id: int
    observed_property: str
    release_status: str
    value: float | None
    unit: str | None


class CreateGroundwaterLevelObservation(CreateBaseObservation):
    measuring_point_height: float
    level_status: str


class CreateWaterChemistryObservation(CreateBaseObservation):
    pass


class CreateGeothermalObservation(CreateBaseObservation):
    observation_depth: float


# -------- UPDATE ------------


class UpdateBaseObservation(ValidateObservation):
    observation_datetime: Annotated[AwareDatetime, PastDatetime()]
    sample_id: int | None = None
    field_sample_id: str | None = None
    sensor_id: int | None = None
    observed_property: str | None = None
    release_status: str | None = None
    value: float | None | None = None
    unit: str | None = None


class UpdateGroundwaterLevelObservation(UpdateBaseObservation):
    measuring_point_height: float | None = None
    level_status: str | None = None


class UpdateWaterChemistryObservation(UpdateBaseObservation):
    pass


class UpdateGeothermalObservation(UpdateBaseObservation):
    observation_depth: float | None = None


# -------- RESPONSE ----------
class BaseObservationResponse(BaseModel):
    id: int
    sample_id: int
    sensor_id: int
    observation_datetime: AwareDatetime
    observed_property: str
    created_at: AwareDatetime
    release_status: str
    value: float | None


class GroundwaterLevelObservationResponse(BaseObservationResponse):
    depth_to_water_bgs: float | None
    measuring_point_height: float
    level_status: str | None

    @field_validator("depth_to_water_bgs")
    def calculate_depth_to_water_bgs(cls, depth_to_water_bgs, data):
        depth_to_water = data.values.get("value")
        measuring_point_height = data.values.get("measuring_point_height")
        if depth_to_water is not None:
            return depth_to_water - measuring_point_height
        else:
            return depth_to_water


class WaterChemistryObservationResponse(BaseObservationResponse):
    pass


class GeothermalObservationResponse(BaseObservationResponse):
    observation_depth: float


class ObservationResponse(
    GroundwaterLevelObservationResponse, GeothermalObservationResponse
):
    """
    Response model for observations.
    Combines groundwater level and geothermal observation responses.
    """


# ============= EOF =============================================
