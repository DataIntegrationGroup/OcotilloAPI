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
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from db import adder, get_db_session
from db.chemistry import WaterChemistryAnalysis, WaterChemistryAnalysisSet
from schemas.chemistry_create import CreateWaterChemistryAnalysis, CreateAnalysisSet

router = APIRouter(
    prefix="/chemistry",
)


@router.get("/analysis", tags=["chemistry"])
async def get_chemistry_analysis():
    """
    Retrieve chemistry analysis data.
    """
    # Placeholder for actual implementation
    return {"message": "Chemistry analysis data retrieved successfully."}


# ====== POST ===============
@router.post("/analysis_set", status_code=status.HTTP_201_CREATED)
async def add_chemistry_analysis_set(
    analysis_set_data: CreateAnalysisSet, session: Session = Depends(get_db_session)
):
    """
    Add a set of new chemistry analyses.
    """
    # Placeholder for actual implementation
    # return {"message": "Chemistry analysis set added successfully.", "data": analysis_data}
    return adder(session, WaterChemistryAnalysisSet, analysis_set_data)


@router.post("/analysis", status_code=status.HTTP_201_CREATED, tags=["chemistry"])
async def add_chemistry_analysis(
    analysis_data: CreateWaterChemistryAnalysis,
    session: Session = Depends(get_db_session),
):
    """
    Add a new chemistry analysis.
    """
    # Placeholder for actual implementation
    # return {"message": "Chemistry analysis added successfully.", "data": analysis_data}
    return adder(session, WaterChemistryAnalysis, analysis_data)


# ============= EOF =============================================
