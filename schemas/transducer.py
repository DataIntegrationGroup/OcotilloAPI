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

from pydantic import BaseModel

from core.enums import DataMaturity, ReviewStatus
from schemas import BaseResponseModel, BaseCreateModel


class TransducerObservationBlockResponse(BaseResponseModel):
    review_status: ReviewStatus
    start_datetime: datetime
    end_datetime: datetime
    parameter_id: int
    # parameter: ParameterResponse


class TransducerObservationResponse(BaseResponseModel):
    value: float
    observation_datetime: datetime
    parameter_id: int
    deployment_id: int
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


# ============= EOF =============================================
