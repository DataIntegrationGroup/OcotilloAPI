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
from services.query_helper import make_query
from api.pagination import CustomPage
from db.base import SampleLocation, Well
from fastapi import APIRouter, Depends, status
from schemas.response.chemistry import (
    WaterChemistryAnalysisResponse,
    WaterChemistryAnalysisSetResponse,
)
from services.geospatial_helper import make_within_wkt
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi_pagination.ext.sqlalchemy import paginate
from db import adder, get_db_session
from db.chemistry import WaterChemistryAnalysis, WaterChemistryAnalysisSet
from schemas.create.chemistry import CreateWaterChemistryAnalysis, CreateAnalysisSet

router = APIRouter(
    prefix="/chemistry",
)


@router.get(
    "/analysis_set",
    response_model=CustomPage[WaterChemistryAnalysisSetResponse],
    tags=["chemistry"],
)
async def get_chemistry_analysis_set(
        query: str = None,
        within: str = None,
        session: Session = Depends(get_db_session)):
    """
    Retrieve chemistry analysis sets.
    """
    sql = select(WaterChemistryAnalysisSet)
    if within:
        sql = sql.join(Well)
        sql = sql.join(SampleLocation)
        sql = make_within_wkt(sql, within)

    if query:
        sql = sql.where(make_query(WaterChemistryAnalysisSet, query))

    return paginate(conn=session, query=sql)


@router.get(
    "/analysis",
    response_model=CustomPage[WaterChemistryAnalysisResponse],
    tags=["chemistry"],
)
async def get_chemistry_analysis(
        query: str = None,
        within: str = None,
        session: Session = Depends(get_db_session)
):
    """
    Retrieve chemistry analysis data.
    """
    sql = select(WaterChemistryAnalysis)
    if within:
        sql = sql.join(WaterChemistryAnalysisSet)
        sql = sql.join(Well)
        sql = sql.join(SampleLocation)
        sql = make_within_wkt(sql, within)

    if query:
        sql = sql.where(make_query(WaterChemistryAnalysis, query))

    return paginate(conn=session, query=sql)


# ====== POST ===============
@router.post("/analysis_set", status_code=status.HTTP_201_CREATED)
async def add_chemistry_analysis_set(
    analysis_set_data: CreateAnalysisSet, session: Session = Depends(get_db_session)
):
    """
    Add a set of new chemistry analyses.
    """
    return adder(session, WaterChemistryAnalysisSet, analysis_set_data)


@router.post("/analysis", status_code=status.HTTP_201_CREATED, tags=["chemistry"])
async def add_chemistry_analysis(
    analysis_data: CreateWaterChemistryAnalysis,
    session: Session = Depends(get_db_session),
):
    """
    Add a new chemistry analysis.
    """
    return adder(session, WaterChemistryAnalysis, analysis_data)


# ============= EOF =============================================
