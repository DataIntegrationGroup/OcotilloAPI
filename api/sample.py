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

from fastapi import APIRouter, Query, Response
from sqlalchemy.exc import IntegrityError, ProgrammingError
from starlette.status import HTTP_201_CREATED, HTTP_409_CONFLICT

from api.pagination import CustomPage
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db.sample import Sample
from schemas import ResourceNotFoundResponse
from schemas.sample import SampleResponse, CreateSample, UpdateSample
from services.query_helper import paginated_all_getter, simple_get_by_id
from services.crud_helper import model_patcher, model_deleter, model_adder
from services.exceptions_helper import PydanticStyleException

router = APIRouter(
    prefix="/sample",
    tags=["sample"],
)


def database_error_handler(
    payload: CreateSample | UpdateSample, error: IntegrityError | ProgrammingError
) -> None:
    """
    Handle errors raised by the database when adding or updating a sample.
    """
    error_message = error.orig.args[0]["M"]
    if (
        error_message
        == 'duplicate key value violates unique constraint "sample_field_sample_id_key"'
    ):
        detail = {
            "loc": ["body", "field_sample_id"],
            "msg": f"Sample with field_sample_id {payload.field_sample_id} already exists.",
            "type": "value_error",
            "input": {"field_sample_id": payload.field_sample_id},
        }
    elif (
        error_message
        == 'insert or update on table "sample" violates foreign key constraint "sample_thing_id_fkey"'
    ):
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} does not exist.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }

    raise PydanticStyleException(status_code=HTTP_409_CONFLICT, detail=[detail])


# ============= Post =============================================
@router.post("", status_code=HTTP_201_CREATED, operation_id="create_sample")
async def add_sample(
    sample_data: CreateSample, session: session_dependency, user: admin_dependency
) -> SampleResponse:
    """
    Endpoint to add a sample.
    """
    try:
        return model_adder(session, Sample, sample_data, user=user)
    except (IntegrityError, ProgrammingError) as e:
        database_error_handler(sample_data, e)


# ============= Update =============================================
@router.patch("/{sample_id}", summary="Update Sample", operation_id="update_sample")
async def update_sample(
    sample_id: int,
    sample_data: UpdateSample,
    session: session_dependency,
    user: editor_dependency,
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
        return model_patcher(session, Sample, sample_id, sample_data, user=user)
    except (IntegrityError, ProgrammingError) as e:
        database_error_handler(sample_data, e)


# ============= Get =============================================
@router.get("", summary="Get Samples", operation_id="get_samples")
async def get_samples(
    session: session_dependency,
    user: viewer_dependency,
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


@router.get("/{sample_id}", summary="Get Sample by ID", operation_id="get_sample_by_id")
async def get_sample_by_id(
    sample_id: int, session: session_dependency, user: viewer_dependency
) -> SampleResponse | ResourceNotFoundResponse:
    """
    Endpoint to retrieve a sample by its ID.
    """
    return simple_get_by_id(session, Sample, sample_id)


# ======= DELETE ===============================================================


@router.delete("/{sample_id}", summary="Delete Sample by ID", operation_id="delete_sample")
async def delete_sample_by_id(
    sample_id: int, session: session_dependency, user: admin_dependency
) -> Response:
    return model_deleter(session, Sample, sample_id)


# # ============= EOF =============================================
