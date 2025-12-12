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
import re
from datetime import datetime, date
from typing import Optional, Annotated, TypeAlias
from schemas import past_or_today_validator, PastOrTodayDatetime

import phonenumbers
import utm
from pydantic import (
    BaseModel,
    model_validator,
    BeforeValidator,
    validate_email,
    AfterValidator,
)

from constants import STATE_CODES
from core.enums import (
    ElevationMethod,
    Role,
    ContactType,
    PhoneType,
    EmailType,
    AddressType,
    WellPurpose as WellPurposeEnum,
    MonitoringFrequency,
)


def empty_str_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def blank_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def owner_default(v):
    v = blank_to_none(v)
    if v is None:
        return "Owner"
    return v


def primary_default(v):
    v = blank_to_none(v)
    if v is None:
        return "Primary"
    return v


US_POSTAL_REGEX = re.compile(r"^\d{5}(-\d{4})?$")


def postal_code_or_none(v):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None

    if not US_POSTAL_REGEX.match(v):
        raise ValueError("Invalid postal code")

    return v


def state_validator(v):
    if v and len(v) != 2:
        raise ValueError("State must be a 2 letter abbreviation")

    if v and v.upper() not in STATE_CODES:
        raise ValueError("State must be a valid US state abbreviation")
    return v


def phone_validator(phone_number_str):
    phone_number_str = phone_number_str.strip()
    if phone_number_str:
        parsed_number = phonenumbers.parse(phone_number_str, "US")
        if phonenumbers.is_valid_number(parsed_number):
            formatted_number = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
            return formatted_number
        else:
            raise ValueError(f"Invalid phone number. {phone_number_str}")


def email_validator_function(email_str):
    if email_str:
        try:
            validate_email(email_str)
            return email_str
        except ValueError as e:
            raise ValueError(f"Invalid email format. {email_str}") from e


# Reusable type
PhoneTypeField: TypeAlias = Annotated[
    Optional[PhoneType], BeforeValidator(blank_to_none)
]
ContactTypeField: TypeAlias = Annotated[
    Optional[ContactType], BeforeValidator(blank_to_none)
]
EmailTypeField: TypeAlias = Annotated[
    Optional[EmailType], BeforeValidator(blank_to_none)
]
AddressTypeField: TypeAlias = Annotated[
    Optional[AddressType], BeforeValidator(blank_to_none)
]
ContactRoleField: TypeAlias = Annotated[Optional[Role], BeforeValidator(blank_to_none)]
OptionalFloat: TypeAlias = Annotated[
    Optional[float], BeforeValidator(empty_str_to_none)
]
MonitoryFrequencyField: TypeAlias = Annotated[
    Optional[MonitoringFrequency], BeforeValidator(blank_to_none)
]
WellPurposeField: TypeAlias = Annotated[
    Optional[WellPurposeEnum], BeforeValidator(blank_to_none)
]
PostalCodeField: TypeAlias = Annotated[
    Optional[str], BeforeValidator(postal_code_or_none)
]
StateField: TypeAlias = Annotated[Optional[str], BeforeValidator(state_validator)]
PhoneField: TypeAlias = Annotated[Optional[str], BeforeValidator(phone_validator)]
EmailField: TypeAlias = Annotated[
    Optional[str], BeforeValidator(email_validator_function)
]

OptionalBool: TypeAlias = Annotated[Optional[bool], BeforeValidator(empty_str_to_none)]
OptionalPastOrTodayDateTime: TypeAlias = Annotated[
    Optional[datetime],
    BeforeValidator(empty_str_to_none),
    AfterValidator(past_or_today_validator),
]
OptionalPastOrTodayDate: TypeAlias = Annotated[
    Optional[date],
    BeforeValidator(empty_str_to_none),
    AfterValidator(past_or_today_validator),
]


# ============= EOF =============================================
class WellInventoryRow(BaseModel):
    # Required fields
    project: str
    well_name_point_id: str
    site_name: str
    date_time: PastOrTodayDatetime
    field_staff: str
    utm_easting: float
    utm_northing: float
    utm_zone: str
    elevation_ft: float
    elevation_method: ElevationMethod
    measuring_point_height_ft: float

    # Optional fields
    field_staff_2: Optional[str] = None
    field_staff_3: Optional[str] = None

    contact_1_name: Optional[str] = None
    contact_1_organization: Optional[str] = None
    contact_1_role: ContactRoleField = None
    contact_1_type: ContactTypeField = None
    contact_1_phone_1: PhoneField = None
    contact_1_phone_1_type: PhoneTypeField = None
    contact_1_phone_2: PhoneField = None
    contact_1_phone_2_type: PhoneTypeField = None
    contact_1_email_1: EmailField = None
    contact_1_email_1_type: EmailTypeField = None
    contact_1_email_2: EmailField = None
    contact_1_email_2_type: EmailTypeField = None
    contact_1_address_1_line_1: Optional[str] = None
    contact_1_address_1_line_2: Optional[str] = None
    contact_1_address_1_type: AddressTypeField = None
    contact_1_address_1_state: StateField = None
    contact_1_address_1_city: Optional[str] = None
    contact_1_address_1_postal_code: PostalCodeField = None
    contact_1_address_2_line_1: Optional[str] = None
    contact_1_address_2_line_2: Optional[str] = None
    contact_1_address_2_type: AddressTypeField = None
    contact_1_address_2_state: StateField = None
    contact_1_address_2_city: Optional[str] = None
    contact_1_address_2_postal_code: PostalCodeField = None

    contact_2_name: Optional[str] = None
    contact_2_organization: Optional[str] = None
    contact_2_role: ContactRoleField = None
    contact_2_type: ContactTypeField = None
    contact_2_phone_1: PhoneField = None
    contact_2_phone_1_type: PhoneTypeField = None
    contact_2_phone_2: PhoneField = None
    contact_2_phone_2_type: PhoneTypeField = None
    contact_2_email_1: EmailField = None
    contact_2_email_1_type: EmailTypeField = None
    contact_2_email_2: EmailField = None
    contact_2_email_2_type: EmailTypeField = None
    contact_2_address_1_line_1: Optional[str] = None
    contact_2_address_1_line_2: Optional[str] = None
    contact_2_address_1_type: AddressTypeField = None
    contact_2_address_1_state: StateField = None
    contact_2_address_1_city: Optional[str] = None
    contact_2_address_1_postal_code: PostalCodeField = None
    contact_2_address_2_line_1: Optional[str] = None
    contact_2_address_2_line_2: Optional[str] = None
    contact_2_address_2_type: AddressTypeField = None
    contact_2_address_2_state: StateField = None
    contact_2_address_2_city: Optional[str] = None
    contact_2_address_2_postal_code: PostalCodeField = None

    directions_to_site: Optional[str] = None
    specific_location_of_well: Optional[str] = None
    repeat_measurement_permission: OptionalBool = None
    sampling_permission: OptionalBool = None
    datalogger_installation_permission: OptionalBool = None
    public_availability_acknowledgement: OptionalBool = None  # TODO: needs a home
    special_requests: Optional[str] = None
    ose_well_record_id: Optional[str] = None
    date_drilled: OptionalPastOrTodayDate = None
    completion_source: Optional[str] = None
    total_well_depth_ft: OptionalFloat = None
    historic_depth_to_water_ft: OptionalFloat = None
    depth_source: Optional[str] = None
    well_pump_type: Optional[str] = None
    well_pump_depth_ft: OptionalFloat = None
    is_open: OptionalBool = None  # TODO: needs a home
    datalogger_possible: OptionalBool = None
    casing_diameter_ft: OptionalFloat = None
    measuring_point_description: Optional[str] = None
    well_purpose: WellPurposeField = None
    well_purpose_2: WellPurposeField = None
    well_hole_status: Optional[str] = None
    monitoring_frequency: MonitoryFrequencyField = None

    result_communication_preference: Optional[str] = None
    contact_special_requests_notes: Optional[str] = None
    sampling_scenario_notes: Optional[str] = None
    well_measuring_notes: Optional[str] = None
    sample_possible: OptionalBool = None  # TODO: needs a home

    # water levels
    sampler: Optional[str] = None
    sample_method: Optional[str] = None
    measurement_date_time: OptionalPastOrTodayDateTime = None
    mp_height: Optional[float] = None
    level_status: Optional[str] = None
    depth_to_water_ft: Optional[float] = None
    data_quality: Optional[str] = None
    water_level_notes: Optional[str] = None  # TODO: needs a home

    @model_validator(mode="after")
    def validate_model(self):

        optional_wl = (
            "sampler",
            "sample_method",
            "measurement_date_time",
            "mp_height",
            "level_status",
            "depth_to_water_ft",
            "data_quality",
            "water_level_notes",
        )

        wl_fields = [getattr(self, a) for a in optional_wl]
        if any(wl_fields):
            if not all(wl_fields):
                raise ValueError("All water level fields must be provided")

        # verify utm in NM
        zone = int(self.utm_zone[:-1])
        northern = self.utm_zone[-1]
        if northern.upper() not in ("S", "N"):
            raise ValueError("Invalid utm zone. Must end in S or N. e.g 13N")

        northern = self.utm_zone[-1] == "N"
        lat, lon = utm.to_latlon(
            self.utm_easting, self.utm_northing, zone, northern=northern
        )
        if not ((31.33 <= lat <= 37.00) and (-109.05 <= lon <= -103.00)):
            raise ValueError(
                f"UTM coordinates are outside of the NM. E={self.utm_easting} N={self.utm_northing}"
                f" Zone={self.utm_zone}"
            )

        required_attrs = ("line_1", "type", "state", "city", "postal_code")
        all_attrs = ("line_1", "line_2", "type", "state", "city", "postal_code")
        for jdx in (1, 2):
            key = f"contact_{jdx}"
            # Check if any contact data is provided
            name = getattr(self, f"{key}_name")
            organization = getattr(self, f"{key}_organization")
            has_contact_data = any(
                [
                    name,
                    organization,
                    getattr(self, f"{key}_role"),
                    getattr(self, f"{key}_type"),
                    *[getattr(self, f"{key}_email_{i}", None) for i in (1, 2)],
                    *[getattr(self, f"{key}_phone_{i}", None) for i in (1, 2)],
                    *[
                        getattr(self, f"{key}_address_{i}_{a}", None)
                        for i in (1, 2)
                        for a in all_attrs
                    ],
                ]
            )

            # If any contact data is provided, both name and organization are required
            if has_contact_data:
                if not name:
                    raise ValueError(
                        f"{key}_name is required when other contact fields are provided"
                    )
                if not organization:
                    raise ValueError(
                        f"{key}_organization is required when other contact fields are provided"
                    )
            for idx in (1, 2):
                if any(getattr(self, f"{key}_address_{idx}_{a}") for a in all_attrs):
                    if not all(
                        getattr(self, f"{key}_address_{idx}_{a}")
                        for a in required_attrs
                    ):
                        raise ValueError("All contact address fields must be provided")

                name = getattr(self, f"{key}_name")
                if name:
                    if not getattr(self, f"{key}_role"):
                        raise ValueError(
                            f"{key}_role must be provided if name is provided"
                        )
                    if not getattr(self, f"{key}_type"):
                        raise ValueError(
                            f"{key}_type must be provided if name is provided"
                        )

                phone = getattr(self, f"{key}_phone_{idx}")
                tag = f"{key}_phone_{idx}_type"
                phone_type = getattr(self, f"{key}_phone_{idx}_type")
                if phone and not phone_type:
                    raise ValueError(
                        f"{tag} must be provided if phone number is provided"
                    )

                email = getattr(self, f"{key}_email_{idx}")
                tag = f"{key}_email_{idx}_type"
                email_type = getattr(self, tag)
                if email and not email_type:
                    raise ValueError(
                        f"{tag} type must be provided if email is provided"
                    )

        return self
