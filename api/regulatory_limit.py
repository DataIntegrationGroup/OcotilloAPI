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
"""Read access to the regulatory and health-based limits table.

Read-only on purpose. The table is a reference vocabulary -- MCLs, SMCLs, state
groundwater quality standards -- and a limit changes when a rule is published,
not when a field crew visits a well. Rows are loaded deliberately, by a data
migration, so nothing here writes. Whoever adds the write path should know that
`limit_source` is a foreign key to lexicon_term and 'EPA' is not a term yet.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Query
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_200_OK

from api.pagination import CustomPage
from core.dependencies import session_dependency, viewer_dependency
from db.parameter import Parameter
from db.regulatory_limit import RegulatoryLimit
from schemas.regulatory_limit import RegulatoryLimitResponse
from services.query_helper import order_sort_filter, simple_get_by_id

router = APIRouter(prefix="/regulatory_limit", tags=["regulatory limit"])


# ====== GET ===================================================================


@router.get("", summary="Get regulatory limits", status_code=HTTP_200_OK)
def get_regulatory_limits(
    session: session_dependency,
    user: viewer_dependency,
    parameter_id: Optional[int] = None,
    parameter_name: Optional[str] = None,
    limit_source: Optional[str] = None,
    limit_type: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
    filter_params: Annotated[list[str] | None, Query(alias="filter")] = None,
) -> CustomPage[RegulatoryLimitResponse]:
    """Retrieve regulatory limits, optionally narrowed to one parameter.

    `parameter_name` takes the lexicon name the chemistry results speak, so a
    consumer holding a result can ask for the limits that apply to it without
    first resolving a parameter id. Several matrices can share a name, which is
    why it is a filter and not a lookup: arsenic in water and arsenic in soil
    are two parameters and can carry different limits.
    """
    sql = select(RegulatoryLimit).options(
        # The response nests the parameter, so load them in one extra query
        # rather than one per row.
        selectinload(RegulatoryLimit.parameter)
    )

    if parameter_id is not None:
        sql = sql.where(RegulatoryLimit.parameter_id == parameter_id)

    if parameter_name is not None:
        sql = sql.join(Parameter).where(Parameter.parameter_name == parameter_name)

    if limit_source is not None:
        sql = sql.where(RegulatoryLimit.limit_source == limit_source)

    if limit_type is not None:
        sql = sql.where(RegulatoryLimit.limit_type == limit_type)

    sql = order_sort_filter(
        sql, RegulatoryLimit, sort=sort, order=order, filters=filter_params
    )
    return paginate(conn=session, query=sql)


@router.get(
    "/{regulatory_limit_id}",
    summary="Get a regulatory limit",
    status_code=HTTP_200_OK,
)
def get_regulatory_limit(
    regulatory_limit_id: int,
    session: session_dependency,
    user: viewer_dependency,
) -> RegulatoryLimitResponse:
    """
    Retrieve a regulatory limit by its ID.
    """
    return simple_get_by_id(session, RegulatoryLimit, regulatory_limit_id)


# ============= EOF =============================================
