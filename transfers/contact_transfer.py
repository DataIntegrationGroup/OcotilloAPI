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
from transfers.util import read_csv, filter_to_valid_point_ids
from db import Thing, Contact, ThingContactAssociation, Email, Phone, Address

from schemas.contact import CreateContact


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

    odf = read_csv("ownersdata.csv")
    odf = odf.replace(pd.NA, None)
    odf = odf.replace({np.nan: None})
    odf = filter_to_valid_point_ids(session, odf)
    for i, row in odf.iterrows():
        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        if thing is None:
            print(f"Thing with PointID {row.PointID} not found. Skipping owner.")
            continue

        # TODO: extract role from OwnerComment
        # role = extract_owner_role(row.OwnerComment)
        role = "Owner"
        release_status = "private"

        # TODO: put in guards for null values
        try:

            if row.FirstName is None and row.LastName is None:
                name = None
            elif row.FirstName is not None and row.LastName is None:
                name = row.FirstName
            elif row.FirstName is None and row.LastName is not None:
                name = row.LastName
            else:
                name = f"{row.FirstName} {row.LastName}"

            first_contact_data = {
                "thing_id": thing.id,
                "release_status": release_status,
                "name": name,
                "role": role,
                "contact_type": "Primary",
                "organization": row.Company,
                "nma_pk_owners": row.OwnerKey,
            }

            CreateContact.model_validate(first_contact_data)

            first_contact_data.pop("thing_id")
            first_contact = Contact(**first_contact_data)

            assoc = ThingContactAssociation()
            assoc.thing = thing
            assoc.contact = first_contact

            if row.Email:
                first_contact.emails.append(
                    Email(
                        email=row.Email,
                        email_type="Primary",
                        release_status=release_status,
                    )
                )
            if row.Phone:
                first_contact.phones.append(
                    Phone(
                        phone_number=row.Phone,
                        phone_type="Primary",
                        release_status=release_status,
                    )
                )
            if row.CellPhone:
                first_contact.phones.append(
                    Phone(
                        phone_number=row.CellPhone,
                        phone_type="Mobile",
                        release_status=release_status,
                    )
                )

            if row.MailingAddress:
                first_contact.addresses.append(
                    Address(
                        address_line_1=row.MailingAddress,
                        city=row.MailCity,
                        state=row.MailState,
                        postal_code=row.MailZipCode,
                        address_type="Mailing",
                        release_status=release_status,
                    )
                )

                first_contact.addresses.append(
                    Address(
                        address_line_1=row.PhysicalAddress,
                        city=row.PhysicalCity,
                        state=row.PhysicalState,
                        postal_code=row.PhysicalZipCode,
                        address_type="Physical",
                        release_status=release_status,
                    )
                )

            session.add(assoc)
            session.add(first_contact)
            session.commit()

        except Exception as e:
            print(
                f"Skipping first contact for PointID {row.PointID} due to validation error: {e}"
            )
            from pprint import pprint

            pprint(e)
            session.rollback()

        try:
            if row.SecondFirstName is None and row.SecondLastName is None:
                name = None
            elif row.SecondFirstName is not None and row.SecondLastName is None:
                name = row.SecondFirstName
            elif row.SecondFirstName is None and row.SecondLastName is not None:
                name = row.SecondLastName
            else:
                name = f"{row.SecondFirstName} {row.SecondLastName}"

            second_contact_data = {
                "thing_id": thing.id,
                "release_status": release_status,
                "name": name,
                "role": "Owner",
                "contact_type": "Secondary",
                "organization": row.Company,
                "nma_pk_owners": row.OwnerKey,
            }

            CreateContact.model_validate(second_contact_data)

            second_contact_data.pop("thing_id")
            second_contact = Contact(**second_contact_data)

            assoc = ThingContactAssociation()
            assoc.thing = thing
            assoc.contact = second_contact

            if row.SecondCtctEmail:
                second_contact.emails.append(
                    Email(
                        email=row.SecondCtctEmail,
                        email_type="Primary",
                        release_status=release_status,
                    )
                )

            if row.SecondCtctPhone:
                second_contact.phones.append(
                    Phone(
                        phone_number=row.SecondCtctPhone,
                        phone_type="Primary",
                        release_status=release_status,
                    )
                )

            session.add(assoc)
            session.add(second_contact)

        except Exception as e:
            print(
                f"Skipping second contact for PointID {row.PointID} due to validation error: {e}"
            )
            session.rollback()


# ============= EOF =============================================
