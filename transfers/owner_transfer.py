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
from pathlib import Path
from transfers.util import read_csv
from db import Thing, Contact, ThingContactAssociation, Email, Phone, Address


def transfer_owners(session):

    odf = read_csv('ownersdata.csv')
    odf = odf.replace(pd.NA, None)
    odf = odf.replace({np.nan: None})

    for i, row in odf.iterrows():
        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        if thing is None:
            print(f"Thing with PointID {row.PointID} not foaund. Skipping owner.")
            continue

        contact1 = Contact(name=f"{row.FirstName} {row.LastName}", role="Primary")
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

        contact2 = Contact(
            name=f"{row.SecondFirstName} {row.SecondLastName}", role="Secondary"
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

        session.commit()


# ============= EOF =============================================
