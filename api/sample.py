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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND

from api.pagination import CustomPage
from core.dependencies import session_dependency
from db import adder
from db.engine import get_db_session
from db.sample import Sample
from schemas_v2 import ResourceNotFoundResponse
from schemas_v2.sample import SampleResponse, CreateSample, UpdateSample
from services.query_helper import paginated_all_getter, simple_get_by_id
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
    return adder(session, Sample, sample_data)


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
    
    
    This is handled by the `model_patcher` function, which excludes unset fields from 
    the update.
    """

    return model_patcher(session, Sample, sample_id, sample_data)


# ============= Get =============================================
@router.get("", summary="Get Samples")
def get_samples(
        session: session_dependency,
        sort: str = None,
        order: str = None,
        filter_: str = Query(alias="filter", default=None)) -> CustomPage[SampleResponse]:
    """
    Endpoint to retrieve samples.
    """

    return paginated_all_getter(session, Sample, sort=sort, order=order, filter_=filter_)

# ============= Get by ID =============================================
@router.get("/{sample_id}", summary="Get Sample by ID")
def get_sample_by_id(
    sample_id: int, session: session_dependency
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to retrieve a sample by its ID.
    """
    return simple_get_by_id(session, Sample, sample_id)



# # ============= EOF =============================================
