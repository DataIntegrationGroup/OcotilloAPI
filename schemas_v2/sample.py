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

from db.engine import session_ctx
from db import Thing, Sensor, Sample


"""
REFACTOR TODO: can we use inheritance for commonly defined fields and then set them as optional 
or not between Create, Update, and Response schemas?
"""


# -------- VALIDATE ----------
class ValidateSample(BaseModel):
    """
    Validator for Sample data for Create and Update schemas.
    """

    @field_validator("field_sample_id", check_fields=False)
    def validate_field_sample_id(cls, field_sample_id: str) -> str:
        """
        Validate that the field_sample_id is unique.
        """
        if field_sample_id is not None:
            with session_ctx() as session:
                existing_sample = (
                    session.query(Sample)
                    .filter_by(field_sample_id=field_sample_id)
                    .first()
                )
                if existing_sample:
                    raise ValueError(
                        f"Field sample ID {field_sample_id} already exists."
                    )
        return field_sample_id

    @field_validator("sensor_id", check_fields=False)
    def validate_sensor_id(cls, sensor_id: int | None) -> int | None:
        """
        Validate that the sensor_idexists in the database.
        """
        if sensor_id is not None:
            with session_ctx() as session:
                sensor = session.get(Sensor, sensor_id)
                if not sensor:
                    raise ValueError(f"Sensor with ID {sensor_id} does not exist.")
        return sensor_id

    @field_validator("thing_id", check_fields=False)
    def validate_thing_id_exists(cls, thing_id: int | None) -> int | None:
        """
        Validate that the thing_id exists in the database.
        """
        if thing_id is not None:
            with session_ctx() as session:
                thing = session.get(Thing, thing_id)
                if not thing:
                    raise ValueError(f"Thing with ID {thing_id} does not exist.")
        return thing_id

    @field_validator("sample_date", check_fields=False)
    def validate_sample_date(cls, sample_date: datetime | None) -> datetime | None:
        """
        Validate that the sample_date is not in the future.
        """
        if sample_date is not None:
            if sample_date > datetime.now(tz=timezone.utc):
                raise ValueError(f"Sample date {sample_date} cannot be in the future.")
        return sample_date

    # # REFACTOR TODO: is below ground negative or positive? the combine this with validate_sample_bottom defined below
    # @field_validator("sample_bottom", check_fields=False)
    # def validate_sample_bottom(cls, sample_bottom: float | None, values) -> float | None:
    #     """
    #     Validate that the sample_bottom is not less than sample_top.
    #     """
    #     sample_top = values.get('sample_top')
    #     if sample_bottom is not None and sample_top is not None:
    #         if sample_bottom > sample_top:
    #             raise ValueError(
    #                 "Sample bottom cannot be greater than sample top."
    #             )
    #     return sample_bottom

    # REFACTOR TODO: fields are evaluated in the order in which they are defined.
    # are sample top/bottom really working as expected?

    @field_validator("sample_top", check_fields=False)
    def validate_sample_top(cls, sample_top: float | None, values) -> float | None:
        """
        Validate that the sample_top is not less than sample_bottom.
        """
        sample_bottom = values.data.get("sample_bottom")
        if sample_bottom is None and sample_top is not None:
            raise ValueError("Sample bottom must be defined if sample top is defined.")
        elif sample_bottom is not None and sample_top is None:
            raise ValueError("Sample top must be defined if sample bottom is defined.")
        return sample_top

    @field_validator("sample_bottom", check_fields=False)
    def validate_sample_bottom(
        cls, sample_bottom: float | None, values
    ) -> float | None:
        """
        Validate that the sample_bottom is defined if sample_top is defined and vice versa
        """
        sample_top = values.data.get("sample_top")
        if sample_bottom is None and sample_top is not None:
            raise ValueError("Sample bottom must be defined if sample top is defined.")
        elif sample_bottom is not None and sample_top is None:
            raise ValueError("Sample top must be defined if sample bottom is defined.")
        return sample_bottom


# -------- CREATE ----------
class CreateSample(ValidateSample):
    thing_id: int
    sample_type: str
    field_sample_id: str
    sample_date: datetime
    release_status: str
    sampler_name: str  # REFACTOR TODO: update with enum/restricted values
    qc_sample: str = "Original"

    sensor_id: int | None = None
    sample_matrix: str | None = (
        None  # REFACTOR TODO: update with enum/restricted values
    )
    sample_method: str | None = (
        None  # REFACTOR TODO: update with enum/restricted values
    )

    duplicate_sample_number: int | None = 0

    # REFACTOR TODO: update with numeric restrictions? Are negative values below ground and positive above?
    # for example: wells below, rain above, and soil/rock could be at ground surface
    sample_top: float | None = None
    sample_bottom: float | None = None


# -------- UPDATE ----------
class UpdateSample(ValidateSample):
    """
    Development notes:

    setting <type> = None makes the field optional, but if it is defined it must be of that type.
    """

    thing_id: int = None  # REFACTOR TODO: should users be able to change this?
    sample_type: str = None
    field_sample_id: str = None
    sample_date: datetime = None
    release_status: str = None
    sampler_name: str = None  # REFACTOR TODO: update with enum/restricted values
    qc_sample: str = None

    sensor_id: int | None = None  # REFACTOR TODO: should users be able to change this?
    sample_matrix: str | None = (
        None  # REFACTOR TODO: update with enum/restricted values
    )
    sample_method: str | None = (
        None  # REFACTOR TODO: update with enum/restricted values
    )

    duplicate_sample_number: int | None = None

    # REFACTOR TODO: update with numeric restrictions? Are negative values below ground and positive above?
    # for example: wells below, rain above, and soil/rock could be at ground surface
    sample_top: float | None = None
    sample_bottom: float | None = None


# -------- RESPONSE ----------
class SampleResponse(BaseModel):
    id: int
    thing_id: int
    sample_type: str
    field_sample_id: str
    sample_date: datetime
    release_status: str
    sampler_name: str
    qc_sample: str

    sensor_id: int | None
    sample_matrix: str | None
    sample_method: str | None

    duplicate_sample_number: int | None

    sample_top: float | None
    sample_bottom: float | None


# ============= EOF =============================================
