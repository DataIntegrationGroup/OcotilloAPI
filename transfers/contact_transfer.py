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
import numpy as np
import pandas as pd
from transfers.util import read_csv, filter_to_valid_point_ids, logger, replace_nans
from db import Thing, Contact, ThingContactAssociation, Email, Phone, Address

from schemas.contact import CreateContact, CreateAddress


def extract_owner_role(comment):
    # if comment is None:
    #     return "Owner"
    # if "Owner" in comment:
    #     return "Owner"
    # if "Manager" in comment:
    #     return "Manager"
    # if "Director" in comment:
    #     return "Director"

    return "Owner"


"""
Developer's notes

Use Pydantic to perform model validations since all restrictions will
be built into the models
"""


def transfer_contacts(session):

    odf = read_csv("OwnersData")
    odf = odf.drop(["OBJECTID", "GlobalID"], axis=1)
    ldf = read_csv("OwnerLink")
    ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1)
    locdf = read_csv("Location")
    ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

    odf = odf.join(ldf.set_index("OwnerKey"), on="OwnerKey")

    odf = replace_nans(odf)

    odf = filter_to_valid_point_ids(session, odf)
    for i, row in odf.iterrows():
        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        logger.info(f"Processing PointID: {i} {row.PointID}")
        if thing is None:
            logger.warning(
                f"Thing with PointID {row.PointID} not found. Skipping owner."
            )
            continue

        try:
            add_first_contact(session, row, thing)
            session.commit()
            session.flush()
            logger.info(f"added first contact for PointID {row.PointID}")
        except Exception as e:
            logger.critical(
                f"Skipping first contact for PointID {row.PointID} due to validation error: {e}"
            )
            from pprint import pprint

            pprint(e)
            session.rollback()

        try:
            add_second_contact(session, row, thing)
            session.commit()
            session.flush()
            logger.info(f"added second contact for PointID {row.PointID}")
        except Exception as e:
            logger.critical(
                f"Skipping second contact for PointID {row.PointID} due to validation error: {e}"
            )
            session.rollback()


def add_first_contact(session, row, thing):
    # TODO: extract role from OwnerComment
    # role = extract_owner_role(row.OwnerComment)
    role = "Owner"
    release_status = "private"

    # TODO: put in guards for null values
    if row.FirstName is None and row.LastName is None:
        name = None
    elif row.FirstName is not None and row.LastName is None:
        name = row.FirstName
    elif row.FirstName is None and row.LastName is not None:
        name = row.LastName
    else:
        name = f"{row.FirstName} {row.LastName}"

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": role,
        "contact_type": "Primary",
        "organization": row.Company,
        "nma_pk_owners": row.OwnerKey,
    }

    contact = _make_contact_and_assoc(session, contact_data, thing)

    if row.Email:
        # TODO: use Pydantic to validate email
        contact.emails.append(
            Email(
                email=row.Email,
                email_type="Primary",
                release_status=release_status,
            )
        )
    if row.Phone:
        # TODO: use Pydantic to validate phone
        contact.phones.append(
            Phone(
                phone_number=row.Phone,
                phone_type="Primary",
                release_status=release_status,
            )
        )
    if row.CellPhone:
        # TODO: use Pydantic to validate cell phone
        contact.phones.append(
            Phone(
                phone_number=row.CellPhone,
                phone_type="Mobile",
                release_status=release_status,
            )
        )

    if row.MailingAddress:
        address_data = {
            "address_line_1": row.MailingAddress,
            "city": row.MailCity,
            "state": row.MailState,
            "postal_code": row.MailZipCode,
            "address_type": "Mailing",
            "release_status": release_status,
        }
        try:
            CreateAddress.model_validate(address_data)
            contact.addresses.append(Address(**address_data))

        except Exception as e:
            logger.warning(
                f"Skipping mailing address for first contact {name}. Validation error: {e}"
            )

    if row.PhysicalAddress:
        try:
            address_data = {
                "address_line_1": row.PhysicalAddress,
                "city": row.PhysicalCity,
                "state": row.PhysicalState,
                "postal_code": row.PhysicalZipCode,
                "address_type": "Physical",
                "release_status": release_status,
            }
            CreateAddress.model_validate(address_data)
            contact.addresses.append(Address(**address_data))
        except Exception as e:
            logger.warning(
                f"Skipping physical address for first contact {name}. Validation error: {e}"
            )


def add_second_contact(session, row, thing):

    release_status = "private"
    if row.SecondFirstName is None and row.SecondLastName is None:
        name = None
    elif row.SecondFirstName is not None and row.SecondLastName is None:
        name = row.SecondFirstName
    elif row.SecondFirstName is None and row.SecondLastName is not None:
        name = row.SecondLastName
    else:
        name = f"{row.SecondFirstName} {row.SecondLastName}"

    contact_data = {
        "thing_id": thing.id,
        "release_status": release_status,
        "name": name,
        "role": "Owner",
        "contact_type": "Secondary",
        "organization": row.Company,
        "nma_pk_owners": row.OwnerKey,
    }

    contact = _make_contact_and_assoc(session, contact_data, thing)

    if row.SecondCtctEmail:
        contact.emails.append(
            Email(
                email=row.SecondCtctEmail,
                email_type="Primary",
                release_status=release_status,
            )
        )

    if row.SecondCtctPhone:
        contact.phones.append(
            Phone(
                phone_number=row.SecondCtctPhone,
                phone_type="Primary",
                release_status=release_status,
            )
        )


def _make_contact_and_assoc(session, data, thing):
    CreateContact.model_validate(data)

    data.pop("thing_id")
    contact = Contact(**data)

    assoc = ThingContactAssociation()
    assoc.thing = thing
    assoc.contact = contact
    session.add(assoc)
    session.add(contact)
    return contact


# ============= EOF =============================================
