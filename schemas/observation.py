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
from pydantic import (
    BaseModel,
    AwareDatetime,
    PastDatetime,
    field_validator,
    model_validator,
)
from typing import Annotated
from typing_extensions import Self

from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel


# class GeothermalMixin:
#     depth: float
#     temperature: float


# -------- VALIDATE -------


class ValidateObservation(BaseModel):
    _observation_class: str
    observed_property: str
    observation_datetime: AwareDatetime

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

    @model_validator(mode="after")
    def prepend_observed_property(self: Self) -> Self:
        observed_property = self.observed_property
        observation_class = self._observation_class
        if observed_property is not None:
            observation_class = self._observation_class
            if not observed_property.startswith(f"{observation_class}:"):
                self.observed_property = f"{observation_class}:{observed_property}"
        return self


# -------- CREATE ----------
class CreateBaseObservation(BaseCreateModel, ValidateObservation):
    observation_datetime: Annotated[AwareDatetime, PastDatetime()]
    sample_id: int | None = None
    sensor_id: int
    observed_property: str
    release_status: str
    value: float | None
    unit: str | None


class CreateGroundwaterLevelObservation(CreateBaseObservation):
    _observation_class: str = "groundwater level"
    measuring_point_height: float
    level_status: str


class CreateWaterChemistryObservation(CreateBaseObservation):
    _observation_class: str = "water chemistry"


class CreateGeothermalObservation(CreateBaseObservation):
    _observation_class: str = "geothermal"
    observation_depth: float


# -------- UPDATE ------------


class UpdateBaseObservation(BaseUpdateModel, ValidateObservation):
    observation_datetime: Annotated[AwareDatetime, PastDatetime()] | None = None
    sample_id: int | None = None
    sensor_id: int | None = None
    observed_property: str | None = None
    release_status: str | None = None
    value: float | None | None = None
    unit: str | None = None


class UpdateGroundwaterLevelObservation(UpdateBaseObservation):
    _observation_class: str = "groundwater level"
    measuring_point_height: float | None = None
    level_status: str | None = None


class UpdateWaterChemistryObservation(UpdateBaseObservation):
    _observation_class: str = "water chemistry"


class UpdateGeothermalObservation(UpdateBaseObservation):
    _observation_class: str = "geothermal"
    observation_depth: float | None = None


# -------- RESPONSE ----------
class BaseObservationResponse(BaseResponseModel):
    sample_id: int
    sensor_id: int
    observation_datetime: AwareDatetime
    observed_property: str
    release_status: str
    value: float | None
    unit: str

    @field_validator("observed_property")
    def remove_observed_property_prefix(cls, v: str) -> str:
        colon_index = v.find(":")
        return v[colon_index + 1 :]


class GroundwaterLevelObservationResponse(BaseObservationResponse):
    depth_to_water_bgs: float | None
    measuring_point_height: float | None
    level_status: str | None

    @model_validator(mode="before")
    def calculate_depth_to_water_bgs(self: Self) -> Self:
        depth_to_water = self.value
        measuring_point_height = self.measuring_point_height
        if depth_to_water is not None and measuring_point_height is not None:
            self.depth_to_water_bgs = depth_to_water - measuring_point_height
        else:
            self.depth_to_water_bgs = None
        return self


class WaterChemistryObservationResponse(BaseObservationResponse):
    pass


class GeothermalObservationResponse(BaseObservationResponse):
    observation_depth: float | None


class ObservationResponse(
    GroundwaterLevelObservationResponse, GeothermalObservationResponse
):
    """
    Response model for observations.
    Combines groundwater level and geothermal observation responses.
    """


# ============= EOF =============================================
