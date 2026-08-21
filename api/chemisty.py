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

from fastapi import APIRouter
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import asc, desc, select

from api.pagination import CustomPage
from core.dependencies import amp_viewer_dependency, session_dependency
from db.chemistry_views import WaterChemistryResultsView
from schemas.chemistry import WaterChemistryResultResponse
from services.legacy_chemistry import canonical_parameter_name

# from services.validation.chemistry import validate_analyte

# from db.chemistry import WaterChemistryAnalysis, WaterChemistryAnalysisSet
# from schemas.create.chemistry import CreateWaterChemistryAnalysis, CreateAnalysisSet

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


@router.get("/results", summary="Get water chemistry results", tags=["chemistry"])
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
        query = query.where(WaterChemistryResultsView.observation_datetime < end_time)

    sort_column = _RESULT_SORT_COLUMNS.get(
        sort or "observation_datetime",
        WaterChemistryResultsView.observation_datetime,
    )
    direction = asc if (order or "desc").lower() == "asc" else desc

    # id is the tiebreaker so paging is stable: without it two analytes sharing
    # a timestamp can swap pages between requests and be served twice or never.
    query = query.order_by(direction(sort_column), WaterChemistryResultsView.id)

    def transformer(rows):
        # Analytes come out of the legacy tables as symbols; the response
        # speaks the lexicon's names so a consumer can match a result to a
        # drinking water standard without knowing the legacy vocabulary.
        return [
            WaterChemistryResultResponse.model_validate(row).model_copy(
                update={"parameter_name": canonical_parameter_name(row.parameter_name)}
            )
            for row in rows
        ]

    return paginate(query=query, conn=session, transformer=transformer)


# @router.get(
#     "/analysis_set",
#     response_model=CustomPage[WaterChemistryAnalysisSetResponse],
#     tags=["chemistry"],
# )
# async def get_chemistry_analysis_set(
#     query: str = None, within: str = None, session: Session = Depends(get_db_session)
# ):
#     """
#     Retrieve chemistry analysis sets.
#     """
#     sql = select(WaterChemistryAnalysisSet)
#     if within:
#         sql = sql.join(Well)
#         sql = sql.join(SampleLocation)
#         sql = make_within_wkt(sql, within)
#
#     if query:
#         sql = sql.where(make_query(WaterChemistryAnalysisSet, query))
#
#     return paginate(conn=session, query=sql)
#
#
# @router.get(
#     "/analysis",
#     response_model=CustomPage[WaterChemistryAnalysisResponse],
#     tags=["chemistry"],
# )
# async def get_chemistry_analysis(
#     query: str = None, within: str = None, session: Session = Depends(get_db_session)
# ):
#     """
#     Retrieve chemistry analysis data.
#     """
#     sql = select(WaterChemistryAnalysis)
#     if within:
#         sql = sql.join(WaterChemistryAnalysisSet)
#         sql = sql.join(Well)
#         sql = sql.join(SampleLocation)
#         sql = make_within_wkt(sql, within)
#
#     if query:
#         sql = sql.where(make_query(WaterChemistryAnalysis, query))
#
#     return paginate(conn=session, query=sql)


# ====== POST ===============
# @router.post("/analysis_set", status_code=status.HTTP_201_CREATED)
# async def add_chemistry_analysis_set(
#     analysis_set_data: CreateAnalysisSet, session: Session = Depends(get_db_session)
# ):
#     """
#     Add a set of new chemistry analyses.
#     """
#     return adder(session, WaterChemistryAnalysisSet, analysis_set_data)
#
#
# @router.post("/analysis", status_code=status.HTTP_201_CREATED, tags=["chemistry"])
# async def add_chemistry_analysis(
#     analysis_data: CreateWaterChemistryAnalysis = Depends(validate_analyte),
#     session: session_dependency
# ):
#     """
#     Add a new chemistry analysis.
#     """
#     return adder(session, WaterChemistryAnalysis, analysis_data)


# ============= EOF =============================================
