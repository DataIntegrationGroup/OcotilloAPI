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

from schemas import ORMBaseModel
from schemas.response.location import SampleLocationResponse



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


class WellScreenResponse(ORMBaseModel):
    """
    Response schema for well screen details.
    """

    id: int
    well_id: int
    screen_depth_bottom: float
    screen_depth_top: float


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
# ============= EOF =============================================