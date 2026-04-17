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
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from core.enums import DataQuality, GroundwaterLevelReason, SampleMethod
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.functional_validators import BeforeValidator

from services.util import normalize_datetime_to_utc

WATER_LEVEL_REQUIRED_FIELDS = [
    "well_name_point_id",
    "field_event_date_time",
    "field_staff",
    "water_level_date_time",
    "measuring_person",
    "sample_method",
]

WATER_LEVEL_HEADER_ALIASES = {
    "measurement_date_time": "water_level_date_time",
    "sampler": "measuring_person",
    "mp_height_ft": "mp_height",
}

WATER_LEVEL_IGNORED_FIELDS = {
    "hold(not saved)",
    "cut(not saved)",
}

SAMPLE_METHOD_ALIASES = {
    "electric tape": "Electric tape measurement (E-probe)",
    "steel tape": "Steel-tape measurement",
}
SAMPLE_METHOD_CANONICAL = {
    value.lower(): value for value in SAMPLE_METHOD_ALIASES.values()
}
GROUNDWATER_LEVEL_REASON_ALIASES = {
    "dry": "Site was dry",
    "obstructed": ("Obstruction was encountered in the well (no level recorded)"),
    "obstruction": ("Obstruction was encountered in the well (no level recorded)"),
    "flowing": (
        "Site was flowing. Water level or head couldn't be measured "
        "w/out additional equipment."
    ),
    "flowing recently": "Site was flowing recently.",
    "pumped": "Site was being pumped",
    "pumped recently": "Site was pumped recently",
    "not affected": "Water level not affected",
    "other": "Other conditions exist that would affect the level (remarks)",
}


def empty_str_to_none(value):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


OptionalText = Annotated[str | None, BeforeValidator(empty_str_to_none)]
OptionalFloat = Annotated[float | None, BeforeValidator(empty_str_to_none)]


def _canonicalize_enum_value(
    value: str | None, enum_cls, field_name: str
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    for item in enum_cls:
        if item.value.lower() == normalized:
            return item.value

    raise ValueError(f"Unknown {field_name}: {value}")


class WaterLevelCsvRow(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    well_name_point_id: str
    field_event_date_time: datetime
    field_staff: str
    field_staff_2: OptionalText = None
    field_staff_3: OptionalText = None
    water_level_date_time: datetime = Field(
        validation_alias=AliasChoices(
            "water_level_date_time",
            "measurement_date_time",
        )
    )
    measuring_person: str = Field(
        validation_alias=AliasChoices("measuring_person", "sampler")
    )
    sample_method: str
    mp_height: OptionalFloat = Field(
        default=None,
        validation_alias=AliasChoices("mp_height", "mp_height_ft"),
    )
    level_status: OptionalText = None
    depth_to_water_ft: OptionalFloat = None
    data_quality: OptionalText = None
    water_level_notes: OptionalText = None

    @property
    def measurement_date_time(self) -> datetime:
        return self.water_level_date_time

    @property
    def sampler(self) -> str:
        return self.measuring_person

    @classmethod
    def required_fields(cls) -> list[str]:
        return list(WATER_LEVEL_REQUIRED_FIELDS)

    @classmethod
    def header_aliases(cls) -> dict[str, str]:
        return dict(WATER_LEVEL_HEADER_ALIASES)

    @classmethod
    def ignored_fields(cls) -> set[str]:
        return set(WATER_LEVEL_IGNORED_FIELDS)

    @staticmethod
    def canonicalize_sample_method(value: str) -> str:
        normalized = value.strip().lower()
        if normalized in SAMPLE_METHOD_ALIASES:
            return SAMPLE_METHOD_ALIASES[normalized]
        if normalized in SAMPLE_METHOD_CANONICAL:
            return SAMPLE_METHOD_CANONICAL[normalized]
        return value.strip()

    @field_validator("sample_method")
    @classmethod
    def normalize_sample_method(cls, value: str) -> str | None:
        return _canonicalize_enum_value(
            cls.canonicalize_sample_method(value),
            SampleMethod,
            "sample_method",
        )

    @field_validator(
        "field_event_date_time",
        "water_level_date_time",
        mode="after",
    )
    @classmethod
    def normalize_datetime_field(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime_to_utc(value)

    @field_validator("depth_to_water_ft")
    @classmethod
    def validate_non_negative_depth_to_water(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("depth_to_water_ft must be greater than or equal to 0")
        return value

    @field_validator("level_status")
    @classmethod
    def normalize_level_status(cls, value: str | None) -> str | None:
        if value is not None:
            value = GROUNDWATER_LEVEL_REASON_ALIASES.get(value.strip().lower(), value)
        return _canonicalize_enum_value(value, GroundwaterLevelReason, "level_status")

    @field_validator("data_quality")
    @classmethod
    def normalize_data_quality(cls, value: str | None) -> str | None:
        return _canonicalize_enum_value(value, DataQuality, "data_quality")

    @model_validator(mode="after")
    def validate_row_constraints(self) -> WaterLevelCsvRow:
        field_staff = [
            staff
            for staff in (self.field_staff, self.field_staff_2, self.field_staff_3)
            if staff
        ]
        if self.measuring_person not in field_staff:
            raise ValueError(
                "measuring_person must match one of field_staff, "
                "field_staff_2, or field_staff_3"
            )

        if self.water_level_date_time < self.field_event_date_time:
            raise ValueError(
                "water_level_date_time must be greater than or equal to "
                "field_event_date_time"
            )

        if self.depth_to_water_ft is None and self.level_status is None:
            raise ValueError("level_status is required when depth_to_water_ft is blank")

        return self


class WaterLevelBulkUploadSummary(BaseModel):
    total_rows_processed: int
    total_rows_imported: int
    validation_errors_or_warnings: int


class WaterLevelBulkUploadRow(BaseModel):
    well_name_point_id: str
    field_event_id: int
    field_activity_id: int
    sample_id: int
    observation_id: int
    measurement_date_time: str
    level_status: str | None
    data_quality: str | None


class WaterLevelBulkUploadResponse(BaseModel):
    summary: WaterLevelBulkUploadSummary
    water_levels: list[WaterLevelBulkUploadRow]
    validation_errors: list[str]


# ============= EOF =============================================
