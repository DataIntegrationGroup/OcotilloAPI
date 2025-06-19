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
from pydantic import model_validator
from schemas import ORMBaseModel


class CreateWell(ORMBaseModel):
    """
    Schema for creating a well.
    """

    location_id: int
    api_id: str | None = None
    ose_pod_id: str | None = None
    well_type: str | None = None
    well_depth: float | None = None  # in feet
    construction_notes: str | None = None


class CreateScreenWell(ORMBaseModel):
    """
    Schema for creating a well screen.
    """

    well_id: int
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
# ============= EOF =============================================
