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

from fastapi import APIRouter, HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import asc, desc, select

from api.pagination import CustomPage
from core.dependencies import amp_viewer_dependency, session_dependency
from db.chemistry_views import WaterChemistryResultsView
from schemas.chemistry import (
    ChemistryDisplayResponse,
    WaterChemistryResultResponse,
)
from services.chemistry_display import build_chemistry_display_payload
from services.legacy_chemistry import canonical_parameter_name, result_kind

router = APIRouter(
    prefix="/chemistry",
)


# Only columns that mean something to a client of this endpoint. A whitelist
# rather than getattr on the view: the latter would expose every column,
# including the ones carrying release state, as a public sort key.
_RESULT_SORT_COLUMNS = {
    "observation_datetime": WaterChemistryResultsView.observation_datetime,
    "parameter_name": WaterChemistryResultsView.parameter_name,
    "value": WaterChemistryResultsView.value,
    "id": WaterChemistryResultsView.id,
}


@router.get(
    "/results",
    summary="Get water chemistry results",
    tags=["chemistry"],
)
def get_water_chemistry_results(
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    sort: str | None = None,
    order: str | None = None,
) -> CustomPage[WaterChemistryResultResponse]:
    """
    Retrieve water chemistry results, one row per analyte.

    Reads the legacy NMA chemistry tables, which is where the water chemistry
    actually is -- the refactored `observation` table holds none of it. Rows
    come from the public view, so an unreleased thing or a sample flagged
    `PublicRelease = false` is not served here regardless of who is asking.

    `start_time` is inclusive and `end_time` exclusive, so a calendar year is
    `start_time=YYYY-01-01&end_time=YYYY+1-01-01` with no risk of picking up a
    result recorded at midnight on New Year's Day of the following year.

    `sort` accepts `observation_datetime`, `parameter_name`, `value`, or `id`;
    `order` accepts `asc` or `desc`. The default is newest first, so a client
    that wants a well's most recent analysis can ask for size 1.
    """
    query = select(WaterChemistryResultsView)

    if thing_id is not None:
        query = query.where(WaterChemistryResultsView.thing_id == thing_id)

    if start_time is not None:
        query = query.where(
            WaterChemistryResultsView.observation_datetime >= start_time
        )

    if end_time is not None:
        observed_at = WaterChemistryResultsView.observation_datetime
        query = query.where(observed_at < end_time)

    sort_column = _RESULT_SORT_COLUMNS.get(
        sort or "observation_datetime",
        WaterChemistryResultsView.observation_datetime,
    )
    direction = asc if (order or "desc").lower() == "asc" else desc

    # id is the tiebreaker so paging is stable: without it two analytes
    # sharing a timestamp can swap pages between requests and be served twice
    # or never.
    query = query.order_by(
        direction(sort_column),
        WaterChemistryResultsView.id,
    )

    def transformer(rows):
        # Analytes come out of the legacy tables as symbols; the response
        # speaks the lexicon's names so a consumer can match a result to a
        # drinking water standard without knowing the legacy vocabulary.
        def response_for(row):
            parameter_name = canonical_parameter_name(row.parameter_name)
            return WaterChemistryResultResponse.model_validate(row).model_copy(
                update={
                    "parameter_name": parameter_name,
                    "result_kind": result_kind(row.id),
                }
            )

        return [response_for(row) for row in rows]

    return paginate(query=query, conn=session, transformer=transformer)


@router.get(
    "/display",
    summary="Get chemistry display data for a well",
    tags=["chemistry"],
)
def get_chemistry_display(
    session: session_dependency,
    user: amp_viewer_dependency,
    thing_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> ChemistryDisplayResponse:
    """
    Retrieve UI-ready chemistry data for the well details chemistry display.

    The payload is grouped by released NMA chemistry sample events and includes
    major chemistry, minor/trace chemistry, and field parameter rows. The
    newest released sample is selected by default.
    """
    payload = build_chemistry_display_payload(
        session,
        thing_id=thing_id,
        start_time=start_time,
        end_time=end_time,
    )
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="No released chemistry display data found for this thing.",
        )
    return payload
