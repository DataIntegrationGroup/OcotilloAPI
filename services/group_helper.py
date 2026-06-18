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

from fastapi import HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from db.group import Group, GroupThingAssociation
from db.thing import Thing
from schemas.group import GroupResponse
from services.audit_helper import audit_add
from services.edit_notification_helper import EditEvent, notify_edit_event
from services.query_helper import order_sort_filter


def _thing_resource_type(thing: Thing) -> str:
    if thing.thing_type == "water well":
        return "well"
    if thing.thing_type == "spring":
        return "spring"
    return "thing"


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


def add_thing_to_group(
    session: Session, group_id: int, thing_id: int, user: dict
) -> GroupThingAssociation:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found.",
        )

    thing = session.get(Thing, thing_id)
    if thing is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Thing with ID {thing_id} not found.",
        )

    existing = session.execute(
        select(GroupThingAssociation).where(
            GroupThingAssociation.group_id == group_id,
            GroupThingAssociation.thing_id == thing_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        msg = f"Thing {thing_id} is already a member of group {group_id}."
        raise HTTPException(status_code=HTTP_409_CONFLICT, detail=msg)

    assoc = GroupThingAssociation(group_id=group_id, thing_id=thing_id)
    audit_add(user, assoc)
    session.add(assoc)
    session.commit()
    session.refresh(assoc)

    thing_label = thing.name or f"Thing {thing_id}"
    group_name = group.name or f"Group {group_id}"
    notify_edit_event(
        user,
        EditEvent(
            action="project_added",
            resource_type=_thing_resource_type(thing),
            resource_id=thing_id,
            resource_label=thing_label,
            summary=f'Added {thing_label} to project "{group_name}"',
            metadata={"group_id": group_id, "group_name": group_name},
        ),
    )
    return assoc


def remove_thing_from_group(
    session: Session,
    group_id: int,
    thing_id: int,
    user: dict | None = None,
) -> None:
    group = session.get(Group, group_id)
    thing = session.get(Thing, thing_id)

    assoc = session.execute(
        select(GroupThingAssociation).where(
            GroupThingAssociation.group_id == group_id,
            GroupThingAssociation.thing_id == thing_id,
        )
    ).scalar_one_or_none()

    if assoc is None:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=(
                f"No association found between group {group_id} "
                f"and thing {thing_id}."
            ),
        )

    session.delete(assoc)
    session.commit()

    if user and thing is not None:
        thing_label = thing.name or f"Thing {thing_id}"
        group_name = (group.name if group else None) or f"Group {group_id}"
        notify_edit_event(
            user,
            EditEvent(
                action="project_removed",
                resource_type=_thing_resource_type(thing),
                resource_id=thing_id,
                resource_label=thing_label,
                summary=f'Removed {thing_label} from project "{group_name}"',
                metadata={"group_id": group_id, "group_name": group_name},
            ),
        )


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
