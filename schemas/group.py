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
from pydantic import BaseModel, field_validator

from schemas import ORMBaseModel
from services.validation.geospatial import validate_wkt_geometry


# -------- CREATE ----------
class CreateGroup(BaseModel):
    """
    Schema for creating a group.
    """

    name: str
    description: str | None = None
    parent_group_id: int | None = None
    project_area: str | None = None

    @classmethod
    @field_validator("project_area")
    def validate_area_is_wkt(cls, wkt):
        return validate_wkt_geometry(wkt)


# -------- RESPONSE --------
class GroupResponse(ORMBaseModel):
    """
    Pydantic model for the response of a group.
    This model can be extended to include additional fields as needed.
    """

    id: int
    name: str
    description: str | None = None
    parent_group_id: int | None = None


# -------- UPDATE ----------
class UpdateGroup(BaseModel):
    """
    Pydantic model for updating a group.
    This model can be extended to include additional fields as needed.
    """

    name: str | None = None
    description: str | None = None
    parent_group_id: int | None = None
    project_area: str | None = None


# ============= EOF =============================================
