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
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator

from core.enums import (
    ElevationMethod,
    Role,
    ContactType,
    PhoneType,
    EmailType,
    AddressType,
    WellPurpose as WellPurposeEnum,
)


# ============= EOF =============================================
class WellInventoryRow(BaseModel):
    # Required fields
    project: str
    well_name_point_id: str
    site_name: str
    date_time: datetime
    field_staff: str
    utm_easting: float
    utm_northing: float
    utm_zone: int
    elevation_ft: float
    elevation_method: ElevationMethod
    measuring_point_height_ft: float

    # Optional fields
    field_staff_2: Optional[str] = None
    field_staff_3: Optional[str] = None
    contact_name: Optional[str] = None
    contact_organization: Optional[str] = None
    contact_role: Optional[Role] = None
    contact_type: Optional[ContactType] = "Primary"
    contact_phone_1: Optional[str] = None
    contact_phone_1_type: Optional[PhoneType] = None
    contact_phone_2: Optional[str] = None
    contact_phone_2_type: Optional[PhoneType] = None
    contact_email_1: Optional[str] = None
    contact_email_1_type: Optional[EmailType] = None
    contact_email_2: Optional[str] = None
    contact_email_2_type: Optional[EmailType] = None
    contact_address_1_line_1: Optional[str] = None
    contact_address_1_line_2: Optional[str] = None
    contact_address_1_type: Optional[AddressType] = None
    contact_address_1_state: Optional[str] = None
    contact_address_1_city: Optional[str] = None
    contact_address_1_postal_code: Optional[str] = None
    contact_address_2_line_1: Optional[str] = None
    contact_address_2_line_2: Optional[str] = None
    contact_address_2_type: Optional[AddressType] = None
    contact_address_2_state: Optional[str] = None
    contact_address_2_city: Optional[str] = None
    contact_address_2_postal_code: Optional[str] = None
    directions_to_site: Optional[str] = None
    specific_location_of_well: Optional[str] = None
    repeat_measurement_permission: Optional[bool] = None
    sampling_permission: Optional[bool] = None
    datalogger_installation_permission: Optional[bool] = None
    public_availability_acknowledgement: Optional[bool] = None
    special_requests: Optional[str] = None
    ose_well_record_id: Optional[str] = None
    date_drilled: Optional[datetime] = None
    completion_source: Optional[str] = None
    total_well_depth_ft: Optional[float] = None
    historic_depth_to_water_ft: Optional[float] = None
    depth_source: Optional[str] = None
    well_pump_type: Optional[str] = None
    well_pump_depth_ft: Optional[float] = None
    is_open: Optional[bool] = None
    datalogger_possible: Optional[bool] = None
    casing_diameter_ft: Optional[float] = None
    measuring_point_description: Optional[str] = None
    well_purpose: Optional[WellPurposeEnum] = None
    well_hole_status: Optional[str] = None
    monitoring_frequency: Optional[str] = None

    @model_validator(mode="after")
    def validate_model(self):
        required_attrs = ("line_1", "type", "state", "city", "postal_code")
        all_attrs = ("line_1", "line_2", "type", "state", "city", "postal_code")
        for idx in (1, 2):
            if any(getattr(self, f"contact_address_{idx}_{a}") for a in all_attrs):
                if not all(
                    getattr(self, f"contact_address_{idx}_{a}") for a in required_attrs
                ):
                    raise ValueError("All contact address fields must be provided")

        if self.contact_phone_1 and not self.contact_phone_1_type:
            raise ValueError("Phone type must be provided if phone number is provided")
        if self.contact_email_1 and not self.contact_email_1_type:
            raise ValueError("Email type must be provided if email is provided")

        return self
