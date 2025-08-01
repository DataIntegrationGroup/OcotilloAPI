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
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator

from db.engine import get_db_session
from db import Thing


# -------- CREATE ----------
class CreateSample(BaseModel):
    collection_timestamp: datetime
    collection_method: str
    thing_id: int
    sample_type: str
    sampler: str | None = None
    release_status: str


class CreateGeochemicalSample(BaseModel):
    """
    Represents a geochemical sample in the collaborative network.
    """

    sample_id: int


class CreateGeothermalSample(BaseModel):
    """
    Represents a geothermal sample in the collaborative network.
    """

    sample_id: int


# -------- RESPONSE ----------
class SampleResponse(BaseModel):
    id: int
    collection_timestamp: datetime
    collection_method: str
    thing_id: int


# -------- UPDATE ----------
class UpdateSample(BaseModel):
    collection_timestamp: datetime | None = None
    collection_method: str | None = None
    thing_id: int | None = None

    @field_validator("thing_id")
    def validate_thing_id_exists(cls, thing_id: int) -> int:
        """
        Validate that the thing_id exists in the database.
        """
        with next(get_db_session()) as session:
            thing = session.get(Thing, thing_id)
            if not thing:
                raise ValueError(f"Thing with ID {thing_id} does not exist.")
        return thing_id

    @field_validator("collection_timestamp")
    def validate_collection_timestamp(cls, collection_timestamp: datetime) -> datetime:
        """
        Validate that the collection_timestamp is not in the future.
        """
        if collection_timestamp:
            if collection_timestamp > datetime.now(tz=timezone.utc):
                raise ValueError(
                    f"Collection timestamp {collection_timestamp} cannot be in the future."
                )
        return collection_timestamp


# ============= EOF =============================================
