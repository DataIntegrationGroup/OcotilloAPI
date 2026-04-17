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

import phonenumbers
import utm
from core.constants import STATE_CODES
from core.enums import (
    ElevationMethod,
    Role,
    ContactType,
    PhoneType,
    EmailType,
    AddressType,
    WellPurpose as WellPurposeEnum,
    MonitoringFrequency,
    OriginType,
    WellPumpType,
    MonitoringStatus,
    SampleMethod,
    DataQuality,
    GroundwaterLevelReason,
)
from phonenumbers import NumberParseException
from pydantic import (
    BaseModel,
    model_validator,
    BeforeValidator,
    validate_email,
    AfterValidator,
    field_validator,
    Field,
    AliasChoices,
)
from schemas import past_or_today_validator, PastOrTodayDatetime
from services.util import normalize_datetime_to_utc


def empty_str_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def blank_to_none(v):
    return empty_str_to_none(v)


def owner_default(v):
    v = blank_to_none(v)
    if v is None:
        return "Owner"
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
    # Allow optional phone fields: treat None or blank as no value.
    if phone_number_str is None:
        return None

    phone_number_str = phone_number_str.strip()
    if phone_number_str:
        try:
            parsed_number = phonenumbers.parse(phone_number_str, "US")
        except NumberParseException as e:
            raise ValueError(f"Invalid phone number. {phone_number_str}") from e

        if phonenumbers.is_valid_number(parsed_number):
            formatted_number = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
            return formatted_number

        raise ValueError(f"Invalid phone number. {phone_number_str}")

    # Explicitly return None for empty strings after stripping.
    return None


def email_validator_function(email_str):
    if email_str:
        try:
            validate_email(email_str)
            return email_str
        except ValueError as e:
            raise ValueError(f"Invalid email format. {email_str}") from e


def flexible_lexicon_validator(enum_cls):
    def validator(v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        if isinstance(v, enum_cls):
            return v

        v_str = str(v).strip().lower()
        for item in enum_cls:
            if item.value.lower() == v_str:
                return item
        return v

    return validator


# Reusable type
PhoneTypeField: TypeAlias = Annotated[
    Optional[PhoneType], BeforeValidator(flexible_lexicon_validator(PhoneType))
]
ContactTypeField: TypeAlias = Annotated[
    Optional[ContactType],
    BeforeValidator(flexible_lexicon_validator(ContactType)),
]
EmailTypeField: TypeAlias = Annotated[
    Optional[EmailType], BeforeValidator(flexible_lexicon_validator(EmailType))
]
AddressTypeField: TypeAlias = Annotated[
    Optional[AddressType], BeforeValidator(flexible_lexicon_validator(AddressType))
]
ContactRoleField: TypeAlias = Annotated[
    Optional[Role], BeforeValidator(flexible_lexicon_validator(Role))
]
OptionalFloat: TypeAlias = Annotated[
    Optional[float], BeforeValidator(empty_str_to_none)
]
MonitoringFrequencyField: TypeAlias = Annotated[
    Optional[MonitoringFrequency],
    BeforeValidator(flexible_lexicon_validator(MonitoringFrequency)),
]
WellPurposeField: TypeAlias = Annotated[
    Optional[WellPurposeEnum],
    BeforeValidator(flexible_lexicon_validator(WellPurposeEnum)),
]
OriginTypeField: TypeAlias = Annotated[
    Optional[OriginType], BeforeValidator(flexible_lexicon_validator(OriginType))
]
WellPumpTypeField: TypeAlias = Annotated[
    Optional[WellPumpType], BeforeValidator(flexible_lexicon_validator(WellPumpType))
]
MonitoringStatusField: TypeAlias = Annotated[
    Optional[MonitoringStatus],
    BeforeValidator(flexible_lexicon_validator(MonitoringStatus)),
]
WellStatusField: TypeAlias = Annotated[
    Optional[MonitoringStatus],
    BeforeValidator(flexible_lexicon_validator(MonitoringStatus)),
]
SampleMethodField: TypeAlias = Annotated[
    Optional[SampleMethod], BeforeValidator(flexible_lexicon_validator(SampleMethod))
]
DataQualityField: TypeAlias = Annotated[
    Optional[DataQuality], BeforeValidator(flexible_lexicon_validator(DataQuality))
]
GroundwaterLevelReasonField: TypeAlias = Annotated[
    Optional[GroundwaterLevelReason],
    BeforeValidator(flexible_lexicon_validator(GroundwaterLevelReason)),
]
PostalCodeField: TypeAlias = Annotated[
    Optional[str], BeforeValidator(postal_code_or_none)
]
StateField: TypeAlias = Annotated[Optional[str], BeforeValidator(state_validator)]
PhoneField: TypeAlias = Annotated[Optional[str], BeforeValidator(phone_validator)]
EmailField: TypeAlias = Annotated[
    Optional[str], BeforeValidator(email_validator_function)
]
OptionalText: TypeAlias = Annotated[Optional[str], BeforeValidator(empty_str_to_none)]

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


class WellInventoryRow(BaseModel):
    # Required fields
    project: str
    well_name_point_id: Optional[str] = None
    date_time: PastOrTodayDatetime
    field_staff: str
    utm_easting: float
    utm_northing: float
    utm_zone: str

    # Optional fields
    site_name: OptionalText = None
    elevation_ft: OptionalFloat = None
    elevation_method: Annotated[
        Optional[ElevationMethod],
        BeforeValidator(flexible_lexicon_validator(ElevationMethod)),
    ] = None
    measuring_point_height_ft: OptionalFloat = None
    field_staff_2: OptionalText = None
    field_staff_3: OptionalText = None

    contact_1_name: OptionalText = None
    contact_1_organization: OptionalText = None
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

    contact_2_name: OptionalText = None
    contact_2_organization: OptionalText = None
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
    public_availability_acknowledgement: OptionalBool = None
    special_requests: Optional[str] = None
    ose_well_record_id: Optional[str] = None
    date_drilled: OptionalPastOrTodayDate = None
    completion_source: OriginTypeField = None
    total_well_depth_ft: OptionalFloat = None
    historic_depth_to_water_ft: OptionalFloat = None
    depth_source: OriginTypeField = None
    well_pump_type: WellPumpTypeField = None
    well_pump_depth_ft: OptionalFloat = None
    is_open: OptionalBool = None
    datalogger_possible: OptionalBool = None
    casing_diameter_ft: OptionalFloat = None
    measuring_point_description: Optional[str] = None
    well_purpose: WellPurposeField = None
    well_purpose_2: WellPurposeField = None
    well_status: WellStatusField = Field(
        default=None,
        validation_alias=AliasChoices("well_status", "well_hole_status"),
    )
    monitoring_frequency: MonitoringFrequencyField = None
    monitoring_status: MonitoringStatusField = None

    result_communication_preference: Optional[str] = None
    contact_special_requests_notes: Optional[str] = None
    sampling_scenario_notes: Optional[str] = None
    well_notes: Optional[str] = None
    water_notes: Optional[str] = None
    well_measuring_notes: Optional[str] = None
    sample_possible: OptionalBool = None

    # water levels
    sampler: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("sampler", "measuring_person"),
    )
    sample_method: SampleMethodField = None
    measurement_date_time: OptionalPastOrTodayDateTime = Field(
        default=None,
        validation_alias=AliasChoices("measurement_date_time", "water_level_date_time"),
    )
    mp_height: OptionalFloat = Field(
        default=None,
        validation_alias=AliasChoices("mp_height", "mp_height_ft"),
    )
    level_status: GroundwaterLevelReasonField = None
    depth_to_water_ft: OptionalFloat = None
    data_quality: DataQualityField = None
    water_level_notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_complete_monitoring_frequency(cls, data):
        """Normalize `Complete` monitoring_frequency by clearing monitoring_frequency and setting monitoring_status to `Not currently monitored`."""
        if not isinstance(data, dict):
            return data

        monitoring_frequency = data.get("monitoring_frequency")
        if (
            isinstance(monitoring_frequency, str)
            and monitoring_frequency.strip().lower() == "complete"
        ):
            normalized = dict(data)
            normalized["monitoring_frequency"] = None
            normalized["monitoring_status"] = "Not currently monitored"
            return normalized

        return data

    @field_validator("date_time", mode="after")
    @classmethod
    def normalize_date_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime_to_utc(value)

    @field_validator("measurement_date_time", mode="after")
    @classmethod
    def normalize_measurement_date_time(cls, v) -> datetime | None:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return normalize_datetime_to_utc(v)

    @model_validator(mode="after")
    def validate_model(self):
        # verify utm in NM
        utm_zone_value = (self.utm_zone or "").upper()
        if utm_zone_value not in ("12N", "13N"):
            raise ValueError("Invalid utm zone. Must be one of: 12N, 13N")

        zone = int(utm_zone_value[:-1])
        northern = True  # only northern hemisphere zones (12N, 13N) are supported
        lat, lon = utm.to_latlon(
            self.utm_easting, self.utm_northing, zone, northern=northern
        )
        if not ((31.33 <= lat <= 37.00) and (-109.05 <= lon <= -103.00)):
            raise ValueError(
                f"UTM coordinates are outside of the NM. E={self.utm_easting} N={self.utm_northing}"
                f" Zone={self.utm_zone}"
            )

        if self.depth_to_water_ft is not None:
            if self.measurement_date_time is None:
                raise ValueError(
                    "water_level_date_time is required when depth_to_water_ft is provided"
                )

        required_attrs = ("line_1", "type", "state", "city", "postal_code")
        all_attrs = ("line_1", "line_2", "type", "state", "city", "postal_code")
        for jdx in (1, 2):
            key = f"contact_{jdx}"
            name = getattr(self, f"{key}_name")
            organization = getattr(self, f"{key}_organization")
            role = getattr(self, f"{key}_role")
            contact_type = getattr(self, f"{key}_type")

            # Treat name or organization as contact data too, so bare contacts
            # still go through the same cross-field rules as fully populated ones.
            has_contact_data = any(
                [
                    name,
                    organization,
                    getattr(self, f"{key}_role"),
                    getattr(self, f"{key}_type"),
                    *[getattr(self, f"{key}_email_{i}") for i in (1, 2)],
                    *[getattr(self, f"{key}_phone_{i}") for i in (1, 2)],
                    *[
                        getattr(self, f"{key}_address_{i}_{a}")
                        for i in (1, 2)
                        for a in all_attrs
                    ],
                ]
            )

            if has_contact_data:
                if not name and not organization:
                    raise ValueError(
                        f"At least one of {key}_name or {key}_organization must be provided"
                    )
                if not role:
                    raise ValueError(
                        f"{key}_role is required when contact data is provided"
                    )
                if not contact_type:
                    raise ValueError(
                        f"{key}_type is required when contact data is provided"
                    )
            for idx in (1, 2):
                if any(getattr(self, f"{key}_address_{idx}_{a}") for a in all_attrs):
                    if not all(
                        getattr(self, f"{key}_address_{idx}_{a}")
                        for a in required_attrs
                    ):
                        raise ValueError("All contact address fields must be provided")

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


# ============= EOF =============================================
