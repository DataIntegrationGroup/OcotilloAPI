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
from fastapi import APIRouter, status
from services.crud_helper import model_adder
from schemas.geochronology import CreateGeochronologyAge
from sqlalchemy import select
from core.dependencies import viewer_dependency, session_dependency

router = APIRouter(prefix="/geochronology", tags=["geochronology"])


@router.post("/age", tags=["geochronology"], status_code=status.HTTP_201_CREATED)
async def create_age(
    user: viewer_dependency, age: CreateGeochronologyAge, session: session_dependency
):
    """
    Create a new geochronology age entry.
    """
    # Placeholder for actual implementation
    # return {"message": "Geochronology age created successfully.", "data": age}
    return model_adder(session, GeochronologyAge, age)


@router.get("/age", tags=["geochronology"])
async def get_geochronology_age(
    user: viewer_dependency, session: session_dependency, method: str = "arar"
):
    """
    Retrieve geochronology age data.
    """
    sql = select(GeochronologyAge)
    return session.scalar(sql).all()

    # Placeholder for actual implementation
    # return {"message": "Geochronology age data retrieved successfully."}


# ============= EOF =============================================
