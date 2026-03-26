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

from datetime import datetime, timezone
from typing import Annotated

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic.functional_validators import BeforeValidator

from services.util import convert_dt_tz_naive_to_tz_aware

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


def empty_str_to_none(value):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


OptionalText = Annotated[str | None, BeforeValidator(empty_str_to_none)]
OptionalFloat = Annotated[float | None, BeforeValidator(empty_str_to_none)]


def _normalize_datetime_to_utc(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    elif not isinstance(value, datetime):
        raise ValueError("value must be a datetime or ISO format string")

    if value.tzinfo is None:
        value = convert_dt_tz_naive_to_tz_aware(value, "America/Denver")

    return value.astimezone(timezone.utc)


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
    def normalize_sample_method(cls, value: str) -> str:
        return cls.canonicalize_sample_method(value)

    @field_validator(
        "field_event_date_time",
        "water_level_date_time",
        mode="before",
    )
    @classmethod
    def normalize_datetime_field(cls, value: datetime | str) -> datetime:
        return _normalize_datetime_to_utc(value)


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
