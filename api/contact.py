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
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from api.pagination import CustomPage
from fastapi_pagination.ext.sqlalchemy import paginate
from db import ThingContactAssociation, Thing
from db.contact import Contact
from db.engine import get_db_session
from schemas.base_responses import ContactResponse
from schemas.create.contact import CreateContact
from services.people_helper import add_contact
from services.query_helper import (
    simple_all_getter,
    simple_get_by_id,
    paginated_all_getter,
)

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post(
    "/",
    summary="Create a new contact",
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    contact_data: CreateContact, session: Session = Depends(get_db_session)
) -> ContactResponse:

    return add_contact(session, contact_data)

    # return adder(session, Contact, contact_data)


@router.get("/", summary="Get contacts")
async def get_contacts(
        thing_id: int | None = None,
    session: Session = Depends(get_db_session),
) -> CustomPage[ContactResponse]:
    """
    Retrieve all contacts from the database.
    :param session:
    :return:
    """
    if thing_id:
        sql = select(Contact)
        sql = sql.join(ThingContactAssociation).join(Thing)
        sql = sql.where(Thing.id == thing_id)
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, Contact)


@router.get("/{contact_id}", summary="Get contact by ID")
async def get_contact_by_id(
    contact_id: int, session: Session = Depends(get_db_session)
) -> ContactResponse:
    """
    Retrieve a contact by ID from the database.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}
    return contact


# ============= EOF =============================================
