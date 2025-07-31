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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder
from db.engine import get_db_session
from db.sample import Sample
from schemas_v2 import ResourceNotFoundResponse
from schemas_v2.sample import SampleResponse, CreateSample, UpdateSample
from services.query_helper import paginated_all_getter
from services.crud_helper import model_patcher

router = APIRouter(
    prefix="/sample",
)


# ============= Post =============================================
@router.post("", status_code=HTTP_201_CREATED)
def add_sample(sample_data: CreateSample, session: session_dependency):
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


# ============= Update =============================================
@router.patch("/{sample_id}", summary="Update Sample")
def update_sample(
    sample_id: int,
    sample_data: UpdateSample,
    session: Session = Depends(get_db_session),
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to update a sample.
    """

    """
    Development notes:

    What do we do if the field is nullable and the schema defaults to None?
    If that occurs, then we update the field to None, which may not have 
    been the intension of the user. We could set some string to indicate
    DO NOT UPDATE. Perhaps coordination between the front and backends?
    """
    if session.get(Sample, sample_id) is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Sample with ID {sample_id} not found.",
        )
    return model_patcher(session, Sample, sample_id, sample_data)


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
def get_sample_by_id(
    sample_id: int, session: session_dependency
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to retrieve a sample by its ID.
    """
    sample = session.get(Sample, sample_id)
    if sample is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Sample with ID {sample_id} not found.",
        )
    else:
        return sample


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
