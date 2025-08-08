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
from typing import List, Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined
from fastapi import APIRouter
from sqlalchemy import select
from starlette import status

from api.pagination import CustomPage
from fastapi_pagination.ext.sqlalchemy import paginate

from core.dependencies import session_dependency
from db import ThingContactAssociation, Thing
from db.contact import Contact, Email, Phone, Address
from schemas.contact import (
    CreateContact,
    PhoneResponse,
    EmailResponse,
    AddressResponse,
    ContactResponse,
    UpdateContact,
    UpdateEmail,
    UpdatePhone,
    UpdateAddress,
)
from services.crud_helper import model_patcher
from services.people_helper import add_contact
from services.query_helper import (
    simple_get_by_id,
    paginated_all_getter,
    order_sort_filter,
)

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post(
    "",
    summary="Create a new contact",
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    contact_data: CreateContact, session: session_dependency
) -> ContactResponse:

    return add_contact(session, contact_data)

    # return adder(session, Contact, contact_data)


@router.patch("/{contact_id}", summary="Update contact")
def update_contact(
    contact_id: int,
    contact_data: UpdateContact,
    session: session_dependency,
) -> ContactResponse:
    """
    Update an existing contact in the database.
    :param contact_id: ID of the contact to update
    :param contact_data: Data to update the contact with
    :param session: Database session
    :return: Updated contact response
    """
    # contact = simple_get_by_id(session, Contact, contact_id)
    # if not contact:
    #     return {"message": "Contact not found"}
    #
    # for key, value in contact_data.model_dump().items():
    #     setattr(contact, key, value)
    #
    # session.commit()
    # session.refresh(contact)

    # return contact
    return model_patcher(session, Contact, contact_id, contact_data)


@router.patch(
    "/email/{email_id}",
)
def update_contact_email(
    email_id: int,
    email_data: UpdateEmail,
    session: session_dependency,
) -> EmailResponse:
    """
    Update an existing contact's email in the database.
    """
    return model_patcher(session, Email, email_id, email_data)


@router.patch(
    "/phone/{phone_id}",
)
def update_contact_phone(
    phone_id: int,
    phone_data: UpdatePhone,
    session: session_dependency,
) -> PhoneResponse:
    """
    Update an existing contact's phone number in the database.
    :param contact_id: ID of the contact to update
    :param phone_type: Type of the phone to update
    :param phone_number: New phone number
    :param session: Database session
    :return: Updated contact response
    """
    return model_patcher(session, Phone, phone_id, phone_data)


@router.patch(
    "/address/{address_id}",
)
def update_contact_address(
    address_id: int,
    address_data: UpdateAddress,
    session: session_dependency,
) -> AddressResponse:
    """
    Update an existing contact's address in the database.

    :param address_id:
    :param address_data:
    :param session:
    :return:
    """
    return model_patcher(session, Address, address_id, address_data)


@router.get("", summary="Get contacts")
async def get_contacts(
    session: session_dependency,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
    thing_id: int | None = None,
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

        sql = order_sort_filter(sql, Contact, sort=sort, order=order, filter_=filter_)
        return paginate(query=sql, conn=session)
    else:
        return paginated_all_getter(session, Contact, sort, order, filter_)


@router.get("/{contact_id}", summary="Get contact by ID")
async def get_contact_by_id(
    contact_id: int, session: session_dependency
) -> ContactResponse:
    """
    Retrieve a contact by ID from the database.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}
    return contact


@router.get("/{contact_id}/email", summary="Get contact emails")
async def get_contact_emails(
    contact_id: int, session: session_dependency
) -> CustomPage[EmailResponse]:
    """
    Retrieve all emails associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}

    sql = select(Email).where(Email.contact_id == contact_id)

    return paginate(query=sql, conn=session)


@router.get("/{contact_id}/phone", summary="Get contact phones")
async def get_contact_phones(
    contact_id: int, session: session_dependency
) -> CustomPage[PhoneResponse]:
    """
    Retrieve all phone numbers associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}
    sql = select(Phone).where(Phone.contact_id == contact_id)
    return paginate(query=sql, conn=session)


@router.get("/{contact_id}/address", summary="Get contact addresses")
async def get_contact_addresses(
    contact_id: int, session: session_dependency
) -> CustomPage[AddressResponse]:
    """
    Retrieve all addresses associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    if not contact:
        return {"message": "Contact not found"}
    sql = select(Address).where(Address.contact_id == contact_id)
    return paginate(query=sql, conn=session)


# ============= EOF =============================================
