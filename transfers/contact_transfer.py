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


def transfer_contacts(session):

    odf = read_csv("OwnersData")
    odf = odf.drop(["OBJECTID", "GlobalID"], axis=1)
    ldf = read_csv("OwnerLink")
    ldf = ldf.drop(["OBJECTID", "GlobalID"], axis=1)
    locdf = read_csv("Location")
    ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

    odf = odf.join(ldf.set_index("OwnerKey"), on="OwnerKey")

    odf = odf.replace(pd.NA, None)
    odf = odf.replace({np.nan: None})
    odf = filter_to_valid_point_ids(session, odf)
    for i, row in odf.iterrows():
        print(f"Transferring contact for PointID {i} {row.PointID}")
        try:
            _iterate(session, row)
            session.commit()
        except Exception as e:
            # TODO: log exception
            print(f"Error iterating row {i}: {e}")
            session.rollback()
            continue


def _iterate(session, row):
    thing = session.query(Thing).where(Thing.name == row.PointID).first()
    if thing is None:
        print(f"Thing with PointID {row.PointID} not foaund. Skipping owner.")
        return

    # TODO: extract role from OwnerComment
    role = extract_owner_role(row.OwnerComment)

    # TODO: put in guards for null values
    # name OR organization must be defined, otherwise skip
    if not (row.FirstName or row.LastName) and not row.Company:
        print(
            f"Skipping first contact for PointID {row.PointID} due to missing name and organization."
        )
    else:
        print(f"Transferring first contact for PointID {row.PointID}")
        contact1 = Contact(
            name=f"{row.FirstName} {row.LastName}",
            role=role,
            # TODO: needs to be implemented
            # priority=1,
            contact_typ="Primary",
            organization=row.Company,  # assumes organization applies to both contacts
            nma_pk_owners=row.OwnerKey,
        )

        assoc = ThingContactAssociation()
        assoc.thing = thing
        assoc.contact = contact1
        session.add(assoc)
        session.add(contact1)

        if row.Email:
            contact1.emails.append(Email(email=row.Email, email_type="Primary"))
        if row.Phone:
            contact1.phones.append(Phone(phone_number=row.Phone, phone_type="Primary"))
        if row.CellPhone:
            contact1.phones.append(
                Phone(phone_number=row.CellPhone, phone_type="Mobile")
            )

        if row.MailingAddress:
            contact1.addresses.append(
                Address(
                    address_line_1=row.MailingAddress,
                    city=row.MailCity,
                    state=row.MailState,
                    postal_code=row.MailZipCode,
                    address_type="Mailing",
                )
            )

            contact1.addresses.append(
                Address(
                    address_line_1=row.PhysicalAddress,
                    city=row.PhysicalCity,
                    state=row.PhysicalState,
                    postal_code=row.PhysicalZipCode,
                    address_type="Physical",
                )
            )

    # TODO: put in guards for null values
    if not (row.SecondFirstName or row.SecondLastName) and not row.Company:
        print(
            f"Skipping second contact for PointID {row.PointID} due to missing name and organization."
        )
    else:
        print(f"Transferring second contact for PointID {row.PointID}")
        contact2 = Contact(
            name=f"{row.SecondFirstName} {row.SecondLastName}",
            role="Owner",  # TODO: role needs to be extracted from somewhere
            contact_type='Secondary',
            # TODO: needs to be implemented
            # priority=2,
            organization=row.Company,  # Assumes organization applies to both contacts
            nma_pk_owners=row.OwnerKey,
        )
        if row.SecondCtctEmail:
            contact2.emails.append(
                Email(email=row.SecondCtctEmail, email_type="Primary")
            )
        if row.SecondCtctPhone:
            contact2.phones.append(
                Phone(phone_number=row.SecondCtctPhone, phone_type="Primary")
            )

        assoc = ThingContactAssociation()
        assoc.thing = thing
        assoc.contact = contact2
        session.add(assoc)
        session.add(contact2)


# ============= EOF =============================================
