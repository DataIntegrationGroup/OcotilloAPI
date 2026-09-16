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
from datetime import datetime, timezone
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
    # When the water was collected. Every result from one sample shares it,
    # which is what lets a client count samples or group results by visit.
    observation_datetime: datetime
    # When the lab ran this result -- often days or weeks after collection, and
    # different for different analytes in the same sample. None for field
    # parameters.
    analysis_date: datetime | None = None
    # Which legacy table the result came from. A field measurement was read at
    # the wellhead and a lab one was not, which is the distinction an
    # owner-facing report has to draw -- and the legacy tables are the only
    # place that distinction is recorded.
    result_kind: Literal["major", "minor", "radionuclide", "field", "unknown"] = (
        "unknown"
    )

    model_config = ConfigDict(from_attributes=True)

    @field_validator("observation_datetime", "analysis_date")
    @classmethod
    def assume_utc(cls, value: datetime | None) -> datetime | None:
        """Stamp naive legacy timestamps as UTC.

        The legacy tables store collection and analysis dates without a zone --
        they are calendar dates, not instants. Attaching UTC keeps them stable:
        `astimezone` on a naive value would read it in the server's local zone,
        which would move a sample collected Jan 01 into the previous year for
        any server west of Greenwich, and a report for that year would then come
        back empty.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("observation_datetime", "analysis_date")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============= EOF =============================================
