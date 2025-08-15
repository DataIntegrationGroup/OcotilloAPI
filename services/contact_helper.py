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
from db.contact import Contact, Email, Phone, Address, ThingContactAssociation
from schemas.contact import (
    CreateAddress,
    CreateContact,
    CreateEmail,
    CreatePhone,
    CreateThingAssociation,
)
from services.audit_helper import audit_add
from sqlalchemy.orm import Session


def add_contact(
    session: Session, contact_data: CreateContact | dict, user: dict
) -> Contact:
    """
    Add a new contact to the database.
    """

    if isinstance(contact_data, CreateContact):
        contact_data = contact_data.model_dump(exclude_unset=True)

    """
    Developer's note

    Rollback if there's an error creating a record in one of the tables so
    that orphaned/fractured records are not made
    """

    try:
        contact = Contact(
            name=contact_data["name"],
            role=contact_data["role"],
        )
        for e in contact_data.get("emails", []):
            email = Email(**e)
            contact.emails.append(email)
            # session.add(email)

        for p in contact_data.get("phones", []):
            phone = Phone(**p)
            contact.phones.append(phone)
            # session.add(phone)

        for a in contact_data.get("addresses", []):
            address = Address(**a)
            contact.addresses.append(address)
            # session.add(address)

        audit_add(user, contact)
        audit_add(user, contact.emails)
        audit_add(user, contact.phones)
        audit_add(user, contact.addresses)

        session.add(contact)
        session.flush()
        session.refresh(contact)

        location_contact_association = ThingContactAssociation()
        location_contact_association.thing_id = contact_data.get("thing_id")
        location_contact_association.contact_id = contact.id

        audit_add(user, location_contact_association)

        session.add(location_contact_association)
        # owner_contact_association = OwnerContactAssociation()
        # owner_contact_association.owner_id = owner.id
        # owner_contact_association.contact_id = contact.id
        # session.add(owner_contact_association)
        session.flush()
        session.commit()
    except Exception as e:
        session.rollback()
        raise e

    return contact


def add_address(
    session: Session, contact_id: int, address_data: dict, user: dict
) -> Address:
    """
    Add an address to a contact.
    """
    if isinstance(address_data, CreateAddress):
        address_data = address_data.model_dump(exclude_unset=True)

    address = Address(**address_data, contact_id=contact_id)
    audit_add(user, address)
    session.add(address)
    session.commit()
    session.refresh(address)

    return address


def add_email(session: Session, contact_id: int, email_data: dict, user: dict) -> Email:
    """
    Add an email to a contact.
    """
    if isinstance(email_data, CreateEmail):
        email_data = email_data.model_dump(exclude_unset=True)

    email = Email(**email_data, contact_id=contact_id)
    audit_add(user, email)
    session.add(email)
    session.commit()
    session.refresh(email)

    return email


def add_phone(session: Session, contact_id: int, phone_data: dict, user: dict) -> Phone:
    """
    Add a phone number to a contact.
    """
    if isinstance(phone_data, CreatePhone):
        phone_data = phone_data.model_dump(exclude_unset=True)

    phone = Phone(**phone_data, contact_id=contact_id)
    audit_add(user, phone)
    session.add(phone)
    session.commit()
    session.refresh(phone)

    return phone


def add_thing_association(
    session: Session, contact_id: int, thing_association_data: dict, user: dict
):
    if isinstance(thing_association_data, CreateThingAssociation):
        thing_association_data = thing_association_data.model_dump(exclude_unset=True)

    thing_association = ThingContactAssociation(
        **thing_association_data, contact_id=contact_id
    )

    audit_add(user, thing_association)

    session.add(thing_association)
    session.commit()
    session.refresh(thing_association)

    return thing_association


# ============= EOF =============================================
