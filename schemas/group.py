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
from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, field_validator, model_validator
from typing_extensions import Self

from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel
from services.validation.geospatial import validate_wkt_geometry


class ValidateGroup(BaseModel):
    project_area: str | None = None
    description: str | None = None
    parent_group_id: int | None = None

    @field_validator("project_area")
    def validate_area_is_wkt(cls, wkt):
        valid_wkt = validate_wkt_geometry(wkt)
        if "MULTIPOLYGON" not in valid_wkt:
            raise ValueError("WKT must be a valid MULTIPOLYGON")

        return valid_wkt


# -------- CREATE ----------
class CreateGroup(BaseCreateModel, ValidateGroup):
    """
    Schema for creating a group.
    """

    name: str


# -------- RESPONSE --------
class GroupResponse(BaseResponseModel):
    """
    Pydantic model for the response of a group.
    This model can be extended to include additional fields as needed.
    """

    name: str
    project_area: str | None
    description: str | None
    parent_group_id: int | None

    @model_validator(mode="before")
    def project_area_to_wkt(self: Self) -> Self:
        if isinstance(self.project_area, WKBElement):
            self.project_area = to_shape(self.project_area).wkt
        return self


# -------- UPDATE ----------
class UpdateGroup(BaseUpdateModel, ValidateGroup):
    """
    Pydantic model for updating a group.
    This model can be extended to include additional fields as needed.
    """

    name: str | None = None


# ============= EOF =============================================
