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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder
from db.engine import get_db_session
from db.sample import Sample
from schemas_v2.sample import (
    SampleResponse,
    CreateSample,
)
from services.query_helper import paginated_all_getter

router = APIRouter(
    prefix="/sample",
)


# ============= Post =============================================
@router.post("", status_code=HTTP_201_CREATED)
def add_sample(sample_data: CreateSample, session: Session = Depends(get_db_session)):
    """
    Endpoint to add a sample.
    """
    # Assuming sample_data is a dictionary with the necessary fields
    # You would typically validate and process this data before adding it to the database
    return adder(session, Sample, sample_data)


# @router.post("/geochemical", status_code=HTTP_201_CREATED)
# def add_geochemical_sample(
#     sample_data: CreateGeochemicalSample, session: Session = Depends(get_db_session)
# ):
#     """
#     Endpoint to add a geochemical sample.
#     """
#     # Assuming sample_data is a dictionary with the necessary fields
#     # You would typically validate and process this data before adding it to the database
#     return adder(session, GeochemicalSample, sample_data)
#
#
# @router.post("/geothermal", status_code=HTTP_201_CREATED)
# def add_geothermal_sample(
#     sample_data: CreateGeothermalSample, session: Session = Depends(get_db_session)
# ):
#     """
#     Endpoint to add a geothermal sample.
#     """
#     # Assuming sample_data is a dictionary with the necessary fields
#     # You would typically validate and process this data before adding it to the database
#     return adder(session, GeothermalSample, sample_data)


# ============= Get =============================================
@router.get("", summary="Get Samples")
def get_samples(session: session_dependency) -> CustomPage[SampleResponse]:
    """
    Endpoint to retrieve samples.
    """
    return paginated_all_getter(session, Sample)


# @router.get(
#     "/geochemical",
#     summary="Get Geochemical Samples",
# )
# def get_geochemical_samples(session: session_dependency) -> CustomPage[SampleResponse]:
#     """
#     Endpoint to retrieve geochemical samples.
#     """
#     return paginated_all_getter(session, GeochemicalSample)
#
#
# @router.get(
#     "/geothermal",
#     summary="Get Geothermal Samples",
# )
# def get_geothermal_samples(session: session_dependency) -> CustomPage[SampleResponse]:
#     """
#     Endpoint to retrieve geothermal samples.
#     """
#     return paginated_all_getter(session, GeothermalSample)


# ============= Get by ID =============================================
@router.get("/{sample_id}", summary="Get Sample by ID")
def get_sample_by_id(sample_id: int, session: session_dependency) -> SampleResponse:
    """
    Endpoint to retrieve a sample by its ID.
    """
    return session.get(Sample, sample_id)


# @router.get("/{sample_id}", summary="Get Geochemical Sample by ID")
# def get_geochemical_sample_by_id(
#     sample_id: int, session: session_dependency
# ) -> SampleResponse:
#     """
#     Endpoint to retrieve a sample by its ID.
#     """
#     return session.get(GeochemicalSample, sample_id)


# @router.get("/{sample_id}", summary="Get Geothermal Sample by ID")
# def get_geothermal_sample_by_id(
#     sample_id: int, session: session_dependency
# ) -> SampleResponse:
#     """
#     Endpoint to retrieve a sample by its ID.
#     """
#     return session.get(GeothermalSample, sample_id)


# # ============= EOF =============================================
