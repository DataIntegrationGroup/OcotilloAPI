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
from datetime import date
from typing import List

from pydantic import BaseModel

from schemas.base_responses import SampleLocationResponse, OwnerResponse


class WFLocation(BaseModel):
    """
    A class representing a geographic location.
    This class is used to validate and process location data.
    """

    point: str  # Assuming point is a string representation of a geographic point (e.g., 'POINT(-105.0 40.0)')
    # You can add more fields as necessary, such as latitude, longitude, etc.


class WFContact(BaseModel):
    """
    A class representing a contact information.
    This class is used to validate and process contact data.
    """

    name: str
    phone: str  # Assuming phone is a string representation of a phone number
    email: str  # Assuming email is a string representation of an email address
    # You can add more fields as necessary, such as address, etc.


class WFOwner(BaseModel):
    """
    A class representing an owner of a well.
    This class is used to validate and process owner data.
    """

    name: str
    contact: list[
        WFContact
    ]  # Assuming contact is a list of dictionaries with phone and email information
    # You can add more fields as necessary, such as address, etc.


class WFWell(BaseModel):
    ose_pod_id: str | None = None  # OSE POD well number, optional
    api_id: str | None = None  # API well number, optional
    usgs_id: str | None = None  # USGS well number, optional

    well_depth: float | None = None  # Depth of the well in feet, optional
    hole_depth: float | None = None  # Depth of the hole in feet, optional
    casing_diameter: float | None = None  # Diameter of the casing in inches, optional
    casing_depth: float | None = None  # Depth of the casing in feet, optional
    casing_description: str | None = None  # Description of the casing, optional
    construction_notes: str | None = None  # Construction notes, optional


class WFGroup(BaseModel):
    name: str
    description: str | None = None


class WellForm(BaseModel):
    """
    A class representing a form for well data submission.
    This class is used to validate and process well data submissions.
    """

    location: WFLocation
    owner: WFOwner
    well: WFWell
    groups: List[WFGroup] | None = None  # Optional group field

    # Define the fields for the well form
    # site_id: str
    # depth_to_water_ftbgs: float
    # date_measured: str  # ISO format date string
    # time_measured: str  # ISO format time string
    # level_status: str
    # data_quality: str
    # measuring_agency: str
    # data_source: str
    # measurement_method: str
    # measured_by: str
    # site_notes: str = None  # Optional field
    # public_release: bool = True  # Default to True


class WellFormResponse(BaseModel):
    """
    A class representing the response for a well form submission.
    This class is used to structure the response data after a successful submission.
    """

    location: SampleLocationResponse
    owner: OwnerResponse
    # You can add more fields to the response as necessary, such as status messages, etc.


class GroundwaterLevelForm(BaseModel):
    """
    A class representing a form for groundwater level data submission.
    This class is used to validate and process groundwater level data submissions.
    """

    well_id: int  # ID of the well
    depth_to_water_bgs: float  # Depth to water below ground surface
    measurement_date: date  # ISO format date string
    notes: str | None = None  # Optional notes field


class GroundwaterLevelFormResponse(BaseModel):
    """
    A class representing the response for a groundwater level form submission.
    This class is used to structure the response data after a successful submission.
    """

    well_id: int
    depth_to_water_bgs: float  # Depth to water below ground surface
    measurement_date: date  # ISO format date string
    notes: str | None = None  # Optional notes field


# ============= EOF =============================================
