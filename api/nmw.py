# ===============================================================================
# Copyright 2026 ross
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
"""NM_Wells (NMW_) staging ingestion endpoints (BDMS-960)."""

from fastapi import APIRouter, Body, HTTPException
from starlette.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from core.dependencies import amp_admin_dependency
from schemas.nmw_submission import NMWBulkUploadResponse, NMWSubmission
from services.nmw_submission import bulk_upload_nmw

router = APIRouter(prefix="/nmw", tags=["nmw"])


@router.post(
    "/bulk-upload",
    response_model=NMWBulkUploadResponse,
    status_code=HTTP_200_OK,
    summary="Bulk-load NM_Wells submissions into the NMW_ staging tables",
)
def bulk_upload_nmw_submissions(
    user: amp_admin_dependency,
    submissions: list[NMWSubmission] = Body(..., min_length=1),
):
    """Accept a spreadsheet-derived batch of wells (one ``NMWSubmission`` per
    well) and load it into the ``NMW_`` staging tables.

    The batch is atomic: if any well fails validation nothing is written and
    the 400 response body carries the same shape as a success (summary + wells
    + validation_errors), so the caller can render every problem at once.
    """

    result = bulk_upload_nmw(submissions)

    if result.exit_code != 0:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=result.payload)

    return result.payload


# ============= EOF =============================================
