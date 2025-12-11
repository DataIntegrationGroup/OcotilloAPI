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
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session, joinedload

from db.contact import Contact, Email, Phone, Address, ThingContactAssociation
from schemas.contact import (
    CreateContact,
)
from services.audit_helper import audit_add
from services.query_helper import order_sort_filter


def get_db_contacts(
    session: Session,
    thing_id: int | None = None,
    sort: str | None = None,
    order: str | None = None,
    filter_: str | None = None,
):
    sql = session.query(Contact).options(
        # eagerly load related tables to avoid N+1 problems
        joinedload(Contact.emails),
        joinedload(Contact.phones),
        joinedload(Contact.addresses),
        joinedload(Contact.thing_associations).joinedload(
            ThingContactAssociation.thing
        ),
        joinedload(Contact.incomplete_nma_phones),
    )

    if thing_id:
        sql = sql.join(ThingContactAssociation)
        sql = sql.where(ThingContactAssociation.thing_id == thing_id)

    sql = order_sort_filter(sql, Contact, sort, order, filter_)
    return paginate(sql)


def add_contact(session: Session, data: CreateContact | dict, user: dict) -> Contact:
    """
    Add a new contact to the database.
    """

    if isinstance(data, CreateContact):
        data = data.model_dump(exclude_unset=True)

    email_data = data.pop("emails", [])
    phone_data = data.pop("phones", [])
    address_data = data.pop("addresses", [])
    thing_id = data.pop("thing_id", None)
    notes_data = data.pop("notes", None)
    contact_data = data

    """
    Developer's note

    Rollback if there's an error creating a record in one of the tables so
    that orphaned/fractured records are not made
    """

    try:
        contact = Contact(**contact_data)
        for e in email_data:
            email = Email(**e)
            contact.emails.append(email)
            # session.add(email)

        for p in phone_data:
            phone = Phone(**p)
            contact.phones.append(phone)
            # session.add(phone)

        for a in address_data:
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
        if thing_id is not None:
            location_contact_association = ThingContactAssociation()
            location_contact_association.thing_id = thing_id
            location_contact_association.contact_id = contact.id

            audit_add(user, location_contact_association)

        session.add(location_contact_association)

        session.flush()
        session.commit()

        if notes_data is not None:
            for n in notes_data:
                note = contact.add_note(n["content"], n["note_type"])
                session.add(note)

        session.commit()
        session.refresh(contact)

        for note in contact.notes:
            session.refresh(note)

    except Exception as e:
        session.rollback()
        raise e

    return contact


# ============= EOF =============================================
