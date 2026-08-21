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

    model_config = ConfigDict(from_attributes=True)

    @field_validator("observation_datetime")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        """Stamp naive legacy timestamps as UTC.

        The legacy tables store collection and analysis dates without a zone --
        they are calendar dates, not instants. Attaching UTC keeps them stable:
        `astimezone` on a naive value would read it in the server's local zone,
        which would move a sample collected Jan 01 into the previous year for
        any server west of Greenwich, and a report for that year would then come
        back empty.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_serializer("observation_datetime")
    def serialize_observation_datetime(self, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============= EOF =============================================
