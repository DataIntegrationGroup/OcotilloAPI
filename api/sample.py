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

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_409_CONFLICT

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
    tags=["sample"],
)


def database_error_handler(
    payload: CreateSample | UpdateSample, error: IntegrityError | ProgrammingError
) -> None:
    """
    Handle database integrity errors.
    """
    error_message = error.orig.args[0]["M"]
    if (
        error_message
        == 'duplicate key value violates unique constraint "sample_field_sample_id_key"'
    ):
        detail = (
            f"Sample with field_sample_id {payload.field_sample_id} already exists."
        )
    elif (
        error_message
        == 'insert or update on table "sample" violates foreign key constraint "sample_thing_id_fkey"'
    ):
        detail = f"Thing with ID {payload.thing_id} does not exist."

    raise HTTPException(status_code=HTTP_409_CONFLICT, detail=detail)


# ============= Post =============================================
@router.post("", status_code=HTTP_201_CREATED)
def add_sample(sample_data: CreateSample, session: session_dependency):
    """
    Endpoint to add a sample.
    """
    try:
        return adder(session, Sample, sample_data)
    except IntegrityError as e:
        database_error_handler(sample_data, e)
    except ProgrammingError as e:
        database_error_handler(sample_data, e)


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
    try:
        return model_patcher(session, Sample, sample_id, sample_data)
    except IntegrityError as e:
        database_error_handler(sample_data, e)
    except ProgrammingError as e:
        database_error_handler(sample_data, e)


# ============= Get =============================================
@router.get("", summary="Get Samples")
def get_samples(
    session: session_dependency,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[SampleResponse]:
    """
    Endpoint to retrieve samples.
    """

    return paginated_all_getter(
        session, Sample, sort=sort, order=order, filter_=filter_
    )


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
