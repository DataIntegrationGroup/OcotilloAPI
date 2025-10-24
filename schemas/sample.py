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
from datetime import timezone
from pydantic import (
    BaseModel,
    field_validator,
    model_validator,
    AwareDatetime,
    PastDatetime,
)
from typing import Annotated
from typing_extensions import Self

from schemas import (
    BaseCreateModel,
    BaseUpdateModel,
    BaseResponseModel,
    UTCAwareDatetime,
)
from schemas.thing import ThingResponse
from schemas.field import FieldEventResponse, FieldActivityResponse
from schemas.contact import ContactResponse


# -------- VALIDATE ----------
class ValidateSample(BaseModel):
    """
    Validator for Sample data for Create and Update schemas.
    """

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

    sample_date: AwareDatetime | None = None
    depth_top: float | None = None
    depth_bottom: float | None = None

    @model_validator(mode="after")
    def validate_top_and_bottom(self) -> Self:
        """
        Validate that depth_top and depth_bottom are both defined or both None.
        """
        depth_top = getattr(self, "depth_top", None)
        depth_bottom = getattr(self, "depth_bottom", None)

        if (depth_top is not None and depth_bottom is None) or (
            depth_top is None and depth_bottom is not None
        ):
            raise ValueError(
                "Depth top and bottom must both be defined or both must be None."
            )
        return self

    @field_validator("sample_date", check_fields=False)
    def convert_sample_date_to_utc(sample_date: AwareDatetime) -> AwareDatetime:
        """
        Convert sample_date to UTC timezone if it's not already. This runs after
        the Annotated validator PastDatetime() is run.
        """
        if sample_date is not None and sample_date.tzinfo != timezone.utc:
            return sample_date.astimezone(timezone.utc)
        return sample_date


# -------- CREATE ----------
class CreateSample(BaseCreateModel, ValidateSample):
    field_activity_id: int
    field_event_participant_id: int
    sample_date: Annotated[AwareDatetime, PastDatetime()]
    sample_name: str
    sample_matrix: str
    sample_method: str
    qc_type: str
    notes: str | None = None
    depth_top: float | None = None
    depth_bottom: float | None = None


# -------- UPDATE ----------
class UpdateSample(BaseUpdateModel, ValidateSample):
    field_activity_id: int | None = None  # TODO: should this be editable?
    field_event_participant_id: int | None = None
    sample_date: Annotated[AwareDatetime, PastDatetime()] | None = None
    sample_name: str | None = None
    sample_matrix: str | None = None
    sample_method: str | None = None
    qc_type: str | None = None
    notes: str | None = None
    depth_top: float | None = None
    depth_bottom: float | None = None


# -------- RESPONSE ----------
class SampleResponse(BaseResponseModel):
    """
    Developer's note

    The frontend uses multiple fields for a thing, field_even, and field_activity,
    which is why full ThingResponse, FieldEventResponse, and FieldActivityResponse
    are returned. If the response becomes too large and slow, we can use
    <model>.model_dump() and exlude fields to reduce the size.
    """

    thing: ThingResponse
    field_event: FieldEventResponse
    field_activity: FieldActivityResponse
    contact: ContactResponse
    sample_date: UTCAwareDatetime
    sample_name: str
    sample_matrix: str
    sample_method: str
    qc_type: str
    notes: str | None
    depth_top: float | None
    depth_bottom: float | None


# ============= EOF =============================================
