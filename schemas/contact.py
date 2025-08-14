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

import phonenumbers
from email_validator import validate_email, EmailNotValidError
from phonenumbers import NumberParseException
from pydantic import field_validator, BaseModel

from schemas import ORMBaseModel
from schemas.thing import ThingResponse


# -------- VALIDATORS ----------


class ValidateEmail(BaseModel):

    email: str | None = None

    @field_validator("email", check_fields=False)
    @classmethod
    def validate_email(cls, email: str | None) -> str | None:
        if email is not None:
            try:
                emailinfo = validate_email(email, check_deliverability=False)
                return emailinfo.normalized
            except EmailNotValidError as e:
                raise ValueError(f"Invalid email format. {email}")


class ValidatePhone(BaseModel):

    phone_number: str | None = None

    @field_validator("phone_number", check_fields=False)
    @classmethod
    def validate_phone(cls, phone_number_str: str | None) -> str | None:
        print(phone_number_str)
        if phone_number_str is not None:
            region = "US"
            try:
                parsed_number = phonenumbers.parse(phone_number_str, region)
                if phonenumbers.is_valid_number(parsed_number):
                    formatted_number = phonenumbers.format_number(
                        parsed_number, phonenumbers.PhoneNumberFormat.E164
                    )
                    return formatted_number
                else:
                    raise ValueError(f"Invalid phone number. {phone_number_str}")
            except NumberParseException as e:
                raise ValueError(f"Invalid phone number. {phone_number_str}")


# -------- CREATE ----------
class CreateEmail(ValidateEmail):
    """
    Schema for creating an email.
    """

    email: str
    email_type: str = "Primary"  # Default to 'Primary'


class CreatePhone(ValidatePhone):
    """
    Schema for creating a phone number.
    """

    phone_number: str
    phone_type: str = "Primary"  # Default to 'Primary'


class CreateAddress(BaseModel):
    """
    Schema for creating an address.
    """

    # todo: use a postal API to validate address and suggest corrections
    address_line_1: str  # Required (e.g., "123 Main St")
    address_line_2: str | None = None  # Optional (e.g., "Apt 4B", "Suite 200")
    city: str
    # todo: add validation.  Should state be required? what about foreign addresses?
    state: str = "NM"  # Default to New Mexico
    postal_code: str
    country: str = "United States"  # Default to United States
    address_type: str = "Primary"


class CreateContact(BaseModel):
    """
    Schema for creating a contact.
    """

    thing_id: int
    name: str
    role: str
    # description: str | None = None
    # email: str | None = None
    # phone: str | None = None

    emails: list[CreateEmail] | None = None
    phones: list[CreatePhone] | None = None
    addresses: list[CreateAddress] | None = None


# -------- RESPONSE ----------
class PhoneResponse(ORMBaseModel):
    """
    Response schema for phone details.
    """

    id: int
    phone_number: str
    phone_type: str  # e.g., 'mobile', 'landline', etc.


class EmailResponse(ORMBaseModel):
    """
    Response schema for email details.
    """

    id: int
    email: str
    email_type: str  # e.g., 'personal', 'work', etc.


class AddressResponse(ORMBaseModel):
    """
    Response schema for address details.
    """

    id: int
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str
    address_type: str


class ContactResponse(ORMBaseModel):
    """
    Response schema for contact details.
    """

    id: int
    name: str
    role: str
    emails: List[EmailResponse] = []
    phones: List[PhoneResponse] = []
    addresses: List[AddressResponse] = []
    things: List[ThingResponse] = []  # List of related things


# -------- UPDATE ----------
class UpdateContact(BaseModel):
    """
    Schema for updating contact information.
    """

    name: str | None = None
    role: str | None = None
    thing_id: int | None = None
    # email: str | None = None
    # phone: str | None = None
    # address: str | None = None


class UpdateEmail(ValidateEmail):
    """
    Schema for updating email information.
    """

    # email: Annotated[Optional[str], None]
    # email_type: Annotated[Optional[str], None]
    email: str | None = None  # None
    email_type: str | None = None  # None


class UpdatePhone(ValidatePhone):
    """
    Schema for updating phone information.
    """

    phone_number: str | None = None
    phone_type: str | None = None


class UpdateAddress(BaseModel):
    """
    Schema for updating address information.
    """

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    address_type: str | None = None


# ============= EOF =============================================
