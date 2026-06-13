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
from typing import Any

from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.group import Group, GroupThingAssociation
from db.thing import Thing
from schemas.group import GroupResponse
from services.query_helper import order_sort_filter


def get_well_counts_by_group_id(
    session: Session, group_ids: list[int]
) -> dict[int, int]:
    if not group_ids:
        return {}

    stmt = (
        select(
            GroupThingAssociation.group_id,
            func.count(Thing.id),
        )
        .join(Thing, GroupThingAssociation.thing_id == Thing.id)
        .where(GroupThingAssociation.group_id.in_(group_ids))
        .where(Thing.thing_type == "water well")
        .group_by(GroupThingAssociation.group_id)
    )
    return {row[0]: int(row[1]) for row in session.execute(stmt).all()}


def group_to_response(group: Group, well_count: int = 0) -> GroupResponse:
    response = GroupResponse.model_validate(group)
    return response.model_copy(update={"well_count": well_count})


def paginated_groups_getter(
    session: Session,
    filter_: str | None = None,
    *,
    filters: list[str] | None = None,
) -> Any:
    sql = select(Group)
    sql = order_sort_filter(sql, Group, None, None, filter_, filters=filters)

    def transformer(groups: list[Group]) -> list[GroupResponse]:
        counts = get_well_counts_by_group_id(session, [group.id for group in groups])
        return [group_to_response(group, counts.get(group.id, 0)) for group in groups]

    return paginate(query=sql, conn=session, transformer=transformer)
