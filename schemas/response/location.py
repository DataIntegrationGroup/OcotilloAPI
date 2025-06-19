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
from pydantic import field_validator
from schemas import ORMBaseModel


class SampleLocationResponse(ORMBaseModel):
    """
    Response schema for sample location details.
    """

    id: int
    name: str | None = None
    description: str | None = None
    point: str

    @field_validator("point", mode="before")
    def point_to_wkt(cls, value):
        if isinstance(value, WKBElement):
            return to_shape(value).wkt

        # If the value is a string, assume it's already in WKT format
        if isinstance(value, str):
            return value


class GroupLocationResponse(ORMBaseModel):
    """
    Response schema for group location details.
    """

    id: int
    group_id: int
    location_id: int


# ============= EOF =============================================
