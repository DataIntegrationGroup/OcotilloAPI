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
from core.enums import LimitType, Unit
from schemas import BaseResponseModel
from schemas.parameter import ParameterResponse


# -------- RESPONSE ----------
class RegulatoryLimitResponse(BaseResponseModel):
    """One citable limit for one parameter.

    The parameter is nested rather than left as a bare id: a consumer reading a
    chemistry result has an analyte *name* from the lexicon (see
    api/chemisty.py), not a parameter id, and a list of limits with only ids in
    it cannot be matched against results without a second round trip.

    ``limit_source`` is a plain string, unlike the other three lexicon-backed
    columns. It is a foreign key to lexicon_term like they are, but no single
    lexicon category collects the issuing agencies -- 'NMED' is an
    `organization` term and 'EPA' is not a term at all yet -- so there is no
    category to build an enum from. Typing it as one of the existing categories
    would reject values the column accepts.
    """

    parameter_id: int
    parameter: ParameterResponse
    limit_source: str
    limit_value: float
    limit_unit: Unit
    limit_type: LimitType | None


# ============= EOF =============================================
