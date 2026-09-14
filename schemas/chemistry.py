# ===============================================================================
# Copyright 2026 ross
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
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class WaterChemistryResultResponse(BaseModel):
    """One legacy chemistry analyte result.

    Not a `BaseResponseModel`: the row comes from a view over the legacy NMA
    tables, so it has a text id rather than an integer one and carries no
    `created_at` of its own.
    """

    id: str
    thing_id: int
    station_name: str | None = None
    sample_id: int | None = None
    parameter_name: str
    value: float | None = None
    unit: str | None = None
    observation_datetime: datetime
    # Which legacy table the result came from. A field measurement was read at
    # the wellhead and a lab one was not, which is the distinction an
    # owner-facing report has to draw -- and the legacy tables are the only
    # place that distinction is recorded.
    result_kind: Literal[
        "major",
        "minor",
        "radionuclide",
        "field",
        "unknown",
    ] = "unknown"

    model_config = ConfigDict(from_attributes=True)

    @field_validator("observation_datetime")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        """Stamp naive legacy timestamps as UTC.

        The legacy tables store collection and analysis dates without a zone --
        they are calendar dates, not instants. Attaching UTC keeps them stable:
        `astimezone` on a naive value would read it in the server's local
        zone, which would move a sample collected Jan 01 into the previous
        year for any server west of Greenwich, and a report for that year
        would then come back empty.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("observation_datetime")
    def serialize_observation_datetime(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ChemistryDisplayStandardResponse(BaseModel):
    """Drinking-water standard comparison for a display result."""

    status: Literal[
        "above_mcl",
        "above_smcl",
        "below_mcl",
        "below_smcl",
        "within_smcl",
        "no_limit",
        "not_compared",
    ]
    label: str
    primary_mcl: float | None = None
    secondary_smcl: float | str | None = None
    unit: str | None = None
    basis: str | None = None


class ChemistryDisplayResultResponse(BaseModel):
    """One chemistry value prepared for the well-details display."""

    id: str
    sample_info_id: int
    source: Literal["major", "minor", "field"]
    parameter_key: str
    parameter_name: str | None = None
    analyte: str | None = None
    symbol: str | None = None
    value: float | None = None
    unit: str | None = None
    uncertainty: float | None = None
    analysis_method: str | None = None
    analysis_date: date | datetime | None = None
    notes: str | None = None
    analyses_agency: str | None = None
    standard: ChemistryDisplayStandardResponse | None = None


class ChemistryDisplaySampleResponse(BaseModel):
    """Sample event metadata for the chemistry display."""

    id: int
    thing_id: int
    label: str
    nma_sample_point_id: str
    nma_wclab_id: str | None = None
    collection_date: datetime | None = None
    collection_method: str | None = None
    collected_by: str | None = None
    analyses_agency: str | None = None
    sample_type: str | None = None
    water_type: str | None = None
    data_source: str | None = None
    data_quality: bool | None = None
    sample_notes: str | None = None

    @field_validator("collection_date")
    @classmethod
    def assume_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("collection_date")
    def serialize_collection_date(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ChemistryDisplayStandardsSummaryResponse(BaseModel):
    """Summary counts for the selected sample's standards table."""

    above_mcl_count: int
    above_smcl_count: int
    compared_parameter_count: int
    latest_analysis_date: date | datetime | None = None


class ChemistryDisplaySectionResponse(BaseModel):
    """All display data for one chemistry section."""

    results: list[ChemistryDisplayResultResponse]


class ChemistryDisplayGeneralResponse(ChemistryDisplaySectionResponse):
    """General chemistry results plus standards summary."""

    standards_summary: ChemistryDisplayStandardsSummaryResponse


class ChemistryDisplayResponse(BaseModel):
    """Chemistry payload for the well details display."""

    samples: list[ChemistryDisplaySampleResponse]
    field_parameters: ChemistryDisplaySectionResponse
    general_chemistry: ChemistryDisplayGeneralResponse
    environmental_tracers: ChemistryDisplaySectionResponse
    additional_analyses: ChemistryDisplaySectionResponse


# ============= EOF =============================================
