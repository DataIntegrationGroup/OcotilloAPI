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
from typing import Annotated, List

from geoalchemy2 import WKBElement
from geoalchemy2.shape import to_shape
from pydantic import ConfigDict, computed_field, field_validator

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


class WellResponse(ORMBaseModel):
    """
    Response schema for well details.
    """

    id: int
    location_id: int
    api_id: str | None = None
    ose_pod_id: str | None = None
    usgs_id: str | None = None
    construction_notes: str | None = None

    # Additional fields can be added as needed


class SampleLocationWellResponse(SampleLocationResponse):
    """
    Response schema for sample location with well details.
    """

    well: List[WellResponse] = []  # List of wells associated with the sample location


class GroupResponse(ORMBaseModel):
    """
    Response schema for group details.
    """

    id: int
    name: str
    description: str | None = None


class ContactResponse(ORMBaseModel):
    """
    Response schema for contact details.
    """

    id: int
    name: str
    email: str | None = None
    phone: str | None = None


class OwnerResponse(ORMBaseModel):
    """
    Response schema for owner details.
    """

    id: int
    name: str
    contacts: List[ContactResponse] = []  # List of contacts associated with the owner
    # email: str | None = None
    # phone: str | None = None


class WellScreenResponse(ORMBaseModel):
    """
    Response schema for well screen details.
    """

    id: int
    well_id: int
    screen_depth_bottom: float
    screen_depth_top: float


class GroupLocationResponse(ORMBaseModel):
    """
    Response schema for group location details.
    """

    id: int
    group_id: int
    location_id: int


class SpringResponse(ORMBaseModel):
    """
    Response schema for spring details.
    """

    id: int
    location_id: int
    description: str | None = None


class EquipmentResponse(ORMBaseModel):
    """
    Response schema for equipment details.
    """

    id: int
    location_id: int
    equipment_type: str | None = None
    model: str | None = None
    serial_no: str | None = None
    date_installed: str | None = None  # ISO format date string
    date_removed: str | None = None  # ISO format date string
    recording_interval: int | None = None
    equipment_notes: str | None = None


# ============= EOF =============================================
