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
"""Geothermal well endpoints.

TEMPORARY BACKING: routes read from the legacy NM_Wells staging mirror
(``db/nmw_legacy.py``) via ``services/geothermal_helper.py``. Once the
NM_Wells -> Ocotillo transform lands these will be backed by the ``thing``
table and ``thing_id`` will be populated on the response. The route path lives
under ``/thing`` so the URL is stable across that swap.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from fastapi_pagination.ext.sqlalchemy import paginate
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from api.pagination import CustomPage
from core.dependencies import session_dependency, viewer_dependency
from schemas.geothermal import GeothermalWellResponse
from services.exceptions_helper import PydanticStyleException
from services.geothermal_helper import (
    geothermal_wells_transformer,
    get_geothermal_well_by_id,
    get_geothermal_wells_query,
)

router = APIRouter(prefix="/thing", tags=["geothermal"])


@router.get(
    "/geothermal-well",
    summary="Get all geothermal wells",
    status_code=HTTP_200_OK,
)
def get_geothermal_wells(
    user: viewer_dependency,
    session: session_dependency,
    county: Optional[str] = None,
    name_contains: Optional[str] = None,
) -> CustomPage[GeothermalWellResponse]:
    """List geothermal wells.

    NOTE: sourced from the legacy NM_Wells mirror (NMW_WellHeaders where
    GthrmExist is set). Will be re-pointed at the thing table post-transform.
    """
    sql = get_geothermal_wells_query(county=county, name_contains=name_contains)
    return paginate(query=sql, conn=session, transformer=geothermal_wells_transformer)


@router.get(
    "/geothermal-well/{well_data_id}",
    summary="Get geothermal well by legacy WellDataID",
    status_code=HTTP_200_OK,
)
def get_geothermal_well(
    user: viewer_dependency,
    well_data_id: UUID,
    session: session_dependency,
) -> GeothermalWellResponse:
    """Get a single geothermal well by its legacy NMW WellDataID (GUID).

    NOTE: keyed by the legacy GUID because these rows are not yet in the thing
    table. Post-transform this becomes an integer thing_id lookup.
    """
    well = get_geothermal_well_by_id(session, well_data_id)
    if well is None:
        raise PydanticStyleException(
            status_code=HTTP_404_NOT_FOUND,
            detail=[
                {
                    "loc": ["path", "well_data_id"],
                    "msg": f"Geothermal well with WellDataID {well_data_id} not found.",
                    "type": "value_error",
                    "input": {"well_data_id": str(well_data_id)},
                }
            ],
        )
    return well


# ============= EOF =============================================
