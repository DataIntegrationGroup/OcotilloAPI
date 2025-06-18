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
from db.geochronology import GeochronologyAge
from fastapi import APIRouter, Depends, status
from db import get_db_session, adder
from schemas.geochronology_create import CreateGeochronologyAge
from sqlalchemy.orm import Session
from sqlalchemy import select

router = APIRouter(
    prefix="/geochronology",
    tags=["geochronology"])

@router.post("/age", tags=["geochronology"], status_code=status.HTTP_201_CREATED)
async def create_age(age: CreateGeochronologyAge, session: Session = Depends(get_db_session)):
    """
    Create a new geochronology age entry.
    """
    # Placeholder for actual implementation
    # return {"message": "Geochronology age created successfully.", "data": age}
    return adder(session, GeochronologyAge, age)


@router.get("/age", tags=["geochronology"])
async def get_geochronology_age(method: str = "arar", session: Session=Depends(get_db_session)):
    """
    Retrieve geochronology age data.
    """
    sql = select(GeochronologyAge)
    return session.scalar(sql).all()

    # Placeholder for actual implementation
    # return {"message": "Geochronology age data retrieved successfully."}
# ============= EOF =============================================
