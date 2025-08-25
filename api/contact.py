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
from fastapi import APIRouter, Query
from fastapi import APIRouter
from sqlalchemy import select
from starlette import status
from sqlalchemy.exc import ProgrammingError
from api.pagination import CustomPage
from fastapi_pagination.ext.sqlalchemy import paginate

from core.dependencies import (
    session_dependency,
    amp_admin_dependency,
    amp_editor_dependency,
    amp_viewer_dependency,
)
from db import ThingContactAssociation, Thing, Contact, Email, Phone, Address, adder
from schemas.contact import (
    CreateContact,
    CreateAddress,
    CreateEmail,
    CreatePhone,
    PhoneResponse,
    EmailResponse,
    AddressResponse,
    ContactResponse,
    UpdateContact,
    UpdateEmail,
    UpdatePhone,
    UpdateAddress,
)
from services.crud_helper import model_patcher, model_deleter
from services.contact_helper import (
    add_contact,
)
from services.query_helper import (
    simple_get_by_id,
    paginated_all_getter,
    order_sort_filter,
)
from services.exceptions_helper import PydanticStyleException

router = APIRouter(prefix="/contact", tags=["contact"])

# ====== DB ERROR HANDLERS =====================================================


def database_error_handler(
    payload: CreateEmail | CreateContact | CreatePhone, error: ProgrammingError
) -> None:
    """
    Handle errors raised by the database when adding or updating a sample.
    """

    error_message = error.orig.args[0]["M"]

    if (
        error_message
        == 'insert or update on table "thing_contact_association" violates foreign key constraint "thing_contact_association_thing_id_fkey"'
    ):
        detail = {
            "loc": ["body", "thing_id"],
            "msg": f"Thing with ID {payload.thing_id} not found.",
            "type": "value_error",
            "input": {"thing_id": payload.thing_id},
        }
    elif (
        error_message
        == 'insert or update on table "email" violates foreign key constraint "email_contact_id_fkey"'
    ):
        detail = {
            "loc": ["body", "contact_id"],
            "msg": f"Contact with ID {payload.contact_id} not found.",
            "type": "value_error",
            "input": {"contact_id": payload.contact_id},
        }
    elif (
        error_message
        == 'insert or update on table "phone" violates foreign key constraint "phone_contact_id_fkey"'
    ):
        detail = {
            "loc": ["body", "contact_id"],
            "msg": f"Contact with ID {payload.contact_id} not found.",
            "type": "value_error",
            "input": {"contact_id": payload.contact_id},
        }
    elif (
        error_message
        == 'insert or update on table "address" violates foreign key constraint "address_contact_id_fkey"'
    ):
        detail = {
            "loc": ["body", "contact_id"],
            "msg": f"Contact with ID {payload.contact_id} not found.",
            "type": "value_error",
            "input": {"contact_id": payload.contact_id},
        }

    raise PydanticStyleException(status_code=status.HTTP_409_CONFLICT, detail=[detail])


# ====== POST ==================================================================


@router.post(
    "",
    summary="Create a new contact",
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    contact_data: CreateContact, session: session_dependency, user: amp_admin_dependency
) -> ContactResponse:
    try:
        return add_contact(session, contact_data, user=user)
    except ProgrammingError as e:
        database_error_handler(contact_data, e)


@router.post(
    "/address",
    summary="Add an address to a contact",
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    address_data: CreateAddress,
    session: session_dependency,
    user: amp_admin_dependency,
) -> AddressResponse:
    """
    Add a new address to an existing contact in the database.
    :param contact_id: ID of the contact to add the address to
    :param address_data: Data for the new address
    :param session: Database session
    :return: Response containing the added address
    """
    try:
        return adder(session, Address, address_data, user=user)
    except ProgrammingError as e:
        database_error_handler(address_data, e)


@router.post(
    "/email",
    summary="Add an email to a contact",
    status_code=status.HTTP_201_CREATED,
)
def create_email(
    email_data: CreateEmail,
    session: session_dependency,
    user: amp_admin_dependency,
) -> EmailResponse:
    try:
        return adder(session, Email, email_data, user=user)
    except ProgrammingError as e:
        database_error_handler(email_data, e)


@router.post(
    "/phone",
    summary="Add a phone number to a contact",
    status_code=status.HTTP_201_CREATED,
)
def create_phone(
    phone_data: CreatePhone,
    session: session_dependency,
    user: amp_admin_dependency,
) -> PhoneResponse:
    try:
        return adder(session, Phone, phone_data, user=user)
    except ProgrammingError as e:
        database_error_handler(phone_data, e)


# @router.post(
#     "/{contact_id}/thing-association",
#     summary="Add a thing-contact association to a contact",
#     status_code=status.HTTP_201_CREATED,
# )
# def add_thing_association_to_contact(
#     contact_id: int,
#     thing_association_data: CreateThingAssociation,
#     session: session_dependency,
#     user: amp_admin_dependency,
# ) -> ThingContactAssociationResponse:
#     contact = simple_get_by_id(session, Contact, contact_id)
#     try:
#         return add_thing_association(
#             session, contact.id, thing_association_data, user=user
#         )
#     except ProgrammingError as e:
#         database_error_handler(thing_association_data, e)


# PATCH ========================================================================


# TODO: catch database errors with patches, most likely foreign key constraints
#   then return a 409 response
@router.patch(
    "/email/{email_id}",
)
def update_contact_email(
    email_id: int,
    email_data: UpdateEmail,
    session: session_dependency,
    user: amp_editor_dependency,
) -> EmailResponse:
    """
    Update an existing contact's email in the database.
    """
    return model_patcher(session, Email, email_id, email_data, user=user)


@router.patch(
    "/phone/{phone_id}",
)
def update_contact_phone(
    phone_id: int,
    phone_data: UpdatePhone,
    session: session_dependency,
    user: amp_editor_dependency,
) -> PhoneResponse:
    """
    Update an existing contact's phone number in the database.
    :param contact_id: ID of the contact to update
    :param phone_type: Type of the phone to update
    :param phone_number: New phone number
    :param session: Database session
    :return: Updated contact response
    """
    return model_patcher(session, Phone, phone_id, phone_data, user=user)


@router.patch(
    "/address/{address_id}",
)
def update_contact_address(
    address_id: int,
    address_data: UpdateAddress,
    session: session_dependency,
    user: amp_editor_dependency,
) -> AddressResponse:
    """
    Update an existing contact's address in the database.

    :param address_id:
    :param address_data:
    :param session:
    :return:
    """
    return model_patcher(session, Address, address_id, address_data, user=user)


# @router.patch(
#     "/thing-association/{thing_contact_association_id}",
#     summary="Update thing-contact association",
# )
# def update_thing_contact_association(
#     thing_contact_association_id: int,
#     thing_contact_association_data: UpdateThingContactAssociation,
#     session: session_dependency,
#     user: amp_editor_dependency,
# ) -> ThingContactAssociationResponse:
#     """
#     Update an existing thing-contact association in the database.

#     :param thing_contact_association_id:
#     :param thing_contact_association_data:
#     :param session:
#     :return:
#     """
#     try:
#         return model_patcher(
#             session,
#             ThingContactAssociation,
#             thing_contact_association_id,
#             thing_contact_association_data,
#             user=user,
#         )
#     except ProgrammingError as e:
#         database_error_handler(thing_contact_association_data, e)


@router.patch("/{contact_id}", summary="Update contact")
def update_contact(
    contact_id: int,
    contact_data: UpdateContact,
    session: session_dependency,
    user: amp_editor_dependency,
) -> ContactResponse:
    """
    Update an existing contact in the database.
    :param contact_id: ID of the contact to update
    :param contact_data: Data to update the contact with
    :param session: Database session
    :return: Updated contact response
    """
    return model_patcher(session, Contact, contact_id, contact_data, user=user)


# ====== GET ===================================================================


@router.get("/email", summary="Get all emails")
async def get_emails(
    session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[EmailResponse]:
    """
    Retrieve all emails from the database.
    :param session:
    :return:
    """
    return paginated_all_getter(session, Email)


@router.get("/email/{email_id}", summary="Get email by ID")
async def get_email_by_id(
    email_id: int, session: session_dependency, user: amp_viewer_dependency
) -> EmailResponse:
    """
    Retrieve an email by ID from the database.
    """
    return simple_get_by_id(session, Email, email_id)


@router.get("/phone", summary="Get all phones")
async def get_phones(
    session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[PhoneResponse]:
    """
    Retrieve all phone numbers from the database.
    :param session:
    :return:
    """
    return paginated_all_getter(session, Phone)


@router.get("/phone/{phone_id}", summary="Get phone by ID")
async def get_phone_by_id(
    phone_id: int, session: session_dependency, user: amp_viewer_dependency
) -> PhoneResponse:
    """
    Retrieve a phone by ID from the database.
    """
    return simple_get_by_id(session, Phone, phone_id)


@router.get("/address", summary="Get all addresses")
async def get_addresses(
    session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[AddressResponse]:
    """
    Retrieve all addresses from the database.
    :param session:
    :return:
    """
    return paginated_all_getter(session, Address)


@router.get("/address/{address_id}", summary="Get address by ID")
async def get_address_by_id(
    address_id: int, session: session_dependency, user: amp_viewer_dependency
) -> AddressResponse:
    """
    Retrieve an address by ID from the database.
    """
    return simple_get_by_id(session, Address, address_id)


# @router.get("/thing-association", summary="Get all thing-contact associations")
# async def get_thing_contact_associations(
#     session: session_dependency, user: amp_viewer_dependency
# ) -> CustomPage[ThingContactAssociationResponse]:
#     """
#     Retrieve all thing-contact associations from the database.
#     :param session:
#     :return:
#     """
#     return paginated_all_getter(session, ThingContactAssociation)


# @router.get(
#     "/thing-association/{thing_contact_association_id}",
#     summary="Get thing-contact association by ID",
# )
# async def get_thing_contact_association_by_id(
#     thing_contact_association_id: int,
#     session: session_dependency,
#     user: amp_viewer_dependency,
# ) -> ThingContactAssociationResponse:
#     """
#     Retrieve a thing-contact association by ID from the database.
#     """
#     return simple_get_by_id(
#         session, ThingContactAssociation, thing_contact_association_id
#     )


@router.get("", summary="Get contacts")
async def get_contacts(
    session: session_dependency,
    user: amp_viewer_dependency,
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
    contact_id: int, session: session_dependency, user: amp_viewer_dependency
) -> ContactResponse:
    """
    Retrieve a contact by ID from the database.
    """
    return simple_get_by_id(session, Contact, contact_id)


@router.get("/{contact_id}/email", summary="Get contact emails")
async def get_contact_emails(
    contact_id: int, session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[EmailResponse]:
    """
    Retrieve all emails associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    sql = select(Email).where(Email.contact_id == contact.id)
    return paginate(query=sql, conn=session)


@router.get("/{contact_id}/phone", summary="Get contact phones")
async def get_contact_phones(
    contact_id: int, session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[PhoneResponse]:
    """
    Retrieve all phone numbers associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    sql = select(Phone).where(Phone.contact_id == contact.id)
    return paginate(query=sql, conn=session)


@router.get("/{contact_id}/address", summary="Get contact addresses")
async def get_contact_addresses(
    contact_id: int, session: session_dependency, user: amp_viewer_dependency
) -> CustomPage[AddressResponse]:
    """
    Retrieve all addresses associated with a contact.
    """
    contact = simple_get_by_id(session, Contact, contact_id)
    sql = select(Address).where(Address.contact_id == contact.id)
    return paginate(query=sql, conn=session)


# @router.get("/{contact_id}/thing-association", summary="Get contact's things")
# async def get_contact_thing_associations(
#     contact_id: int, session: session_dependency, user: amp_viewer_dependency
# ) -> CustomPage[ThingContactAssociationResponse]:
#     """
#     Retrieve all thing-contact associations for a contact.
#     """
#     contact = simple_get_by_id(session, Contact, contact_id)
#     sql = select(ThingContactAssociation).where(
#         ThingContactAssociation.contact_id == contact.id
#     )
#     return paginate(query=sql, conn=session)


# DELETE =======================================================================


@router.delete("/email/{email_id}", summary="Delete contact email")
def delete_contact_email(
    email_id: int, session: session_dependency, user: amp_admin_dependency
):
    """
    Delete a contact email by ID from the database.
    """
    return model_deleter(session, Email, email_id)


@router.delete("/phone/{phone_id}", summary="Delete contact phone")
def delete_contact_phone(
    phone_id: int, session: session_dependency, user: amp_admin_dependency
):
    """
    Delete a contact phone by ID from the database.
    """
    return model_deleter(session, Phone, phone_id)


@router.delete("/address/{address_id}", summary="Delete contact address")
def delete_contact_address(
    address_id: int, session: session_dependency, user: amp_admin_dependency
):
    """
    Delete a contact address by ID from the database.
    """
    return model_deleter(session, Address, address_id)


# @router.delete(
#     "/thing-association/{thing_contact_association_id}",
#     summary="Delete contact thing association",
# )
# def delete_contact_thing_association(
#     thing_contact_association_id: int,
#     session: session_dependency,
#     user: amp_admin_dependency,
# ):
#     """
#     Delete a contact's thing association from the database
#     """
#     return model_deleter(session, ThingContactAssociation, thing_contact_association_id)


@router.delete("/{contact_id}", summary="Delete contact")
def delete_contact(
    contact_id: int, session: session_dependency, user: amp_admin_dependency
):
    """
    Delete a contact by ID from the database.
    """
    return model_deleter(session, Contact, contact_id)


# ============= EOF =============================================
