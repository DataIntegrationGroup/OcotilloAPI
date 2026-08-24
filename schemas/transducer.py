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
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from core.enums import DataMaturity, ReleaseStatus, ReviewStatus
from domain.hydrograph import MAX_MEASUREMENTS, first_out_of_order_index
from schemas import BaseResponseModel, BaseCreateModel


class TransducerObservationBlockResponse(BaseResponseModel):
    review_status: ReviewStatus
    start_datetime: datetime
    end_datetime: datetime
    parameter_id: int
    # parameter: ParameterResponse

    # Publish provenance. Nullable throughout: blocks loaded from the legacy
    # AMPAPI transfer predate the corrector and state none of this.
    source_file: str | None = None
    source_kind: str | None = None
    corrections: list[str] | None = None
    comment: str | None = None


class TransducerObservationResponse(BaseResponseModel):
    value: float
    observation_datetime: datetime
    parameter_id: int
    deployment_id: int
    # Set only where a correction moved the value, so NULL reads as
    # "as measured" rather than "unknown".
    note: str | None = None
    # Nullable: readings loaded before the field existed do not state a
    # maturity, and asserting one for them would be an invention.
    data_maturity: DataMaturity | None


class TransducerObservationWithBlockResponse(BaseModel):
    observation: TransducerObservationResponse
    block: TransducerObservationBlockResponse


class CreateTransducerObservation(BaseCreateModel):

    parameter_id: int
    deployment_id: int
    value: float
    observation_datetime: datetime
    data_maturity: DataMaturity | None = None


# ============= Hydrograph correction publish ====================
# The corrector (OcotilloUI /ocotillo/hydrograph-correction) uploads one
# corrected logger file as one block. See
# docs/hydrograph-correction-publish.md.


class TransducerBlockProvenance(BaseModel):
    """Where a corrected series came from and what was done to it."""

    source_file: str = Field(max_length=255)
    source_kind: Literal["water_head", "depth_to_water"] | None = None
    # Free text in applied order, written by the workbench: "shift (-1.25 ft,
    # ...)", "snap_to_manual (+0.42 ft to ..., collected by ...)".
    corrections: list[str] = Field(default_factory=list)
    notes: str | None = None


class CorrectedMeasurement(BaseModel):
    """One reading of the corrected series, in feet below ground surface."""

    # Aware, so a naive timestamp is rejected rather than guessed at. The
    # workbench sends UTC; a logger file's local wall time silently read as UTC
    # would shift a whole series by hours.
    observation_datetime: AwareDatetime
    value: float
    note: str | None = None

    # NaN and infinity are not measurements. Without this they would validate
    # as floats and land in the column.
    model_config = ConfigDict(allow_inf_nan=False)


class PublishTransducerBlock(BaseCreateModel):
    """A whole corrected file: one block plus every reading in it."""

    thing_id: int
    # Optional: resolved server-side from the block span when omitted, and 422
    # when that is ambiguous. See domain.hydrograph.resolve_deployment_id.
    deployment_id: int | None = None
    parameter_id: int

    # release_status comes from BaseCreateModel, defaulting to "draft".
    review_status: ReviewStatus = "not reviewed"

    provenance: TransducerBlockProvenance
    measurements: list[CorrectedMeasurement] = Field(
        min_length=1, max_length=MAX_MEASUREMENTS
    )

    @field_validator("review_status", mode="before")
    @classmethod
    def coerce_review_status(cls, v):
        if isinstance(v, str):
            try:
                return ReviewStatus(v)
            except ValueError:
                raise ValueError(f"Invalid review_status: {v}")
        return v

    @field_validator("measurements")
    @classmethod
    def measurements_strictly_increasing(cls, measurements):
        # Reported against the offending row's index so the UI can highlight
        # it: the error path becomes
        # ["body", "measurements", N, "observation_datetime"].
        index = first_out_of_order_index(
            [measurement.observation_datetime for measurement in measurements]
        )
        if index is not None:
            raise ValueError(
                f"measurements must be strictly increasing in time; row {index} "
                f"({measurements[index].observation_datetime.isoformat()}) does not "
                f"advance on row {index - 1} "
                f"({measurements[index - 1].observation_datetime.isoformat()})"
            )
        return measurements


class PublishedTransducerBlockResponse(BaseModel):
    """
    Mirrors the read shape so the client can merge a publish straight into a
    ``GET /observation/transducer-groundwater-level`` result set. The
    observations are not echoed -- the client just sent them; the count is what
    it cannot know.
    """

    block: TransducerObservationBlockResponse
    observation_count: int
    thing_id: int
    deployment_id: int


class OverlappingBlock(BaseModel):
    """An existing block a publish would collide with, named in the 409 body."""

    id: int
    start_datetime: datetime
    end_datetime: datetime
    review_status: ReviewStatus
    release_status: ReleaseStatus


class DeletedTransducerObservationsResponse(BaseModel):
    """
    What a range delete removed. ``updated_block_ids`` are blocks that kept
    some readings and had their span narrowed to the survivors.
    """

    deleted_observation_count: int
    deleted_block_ids: list[int]
    updated_block_ids: list[int]
    thing_id: int


# ============= EOF =============================================
