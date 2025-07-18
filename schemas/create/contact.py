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
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from phonenumbers import NumberParseException
from pydantic import field_validator, BaseModel

from schemas import ORMBaseModel


class CreateEmail(BaseModel):
    """
    Schema for creating an email.
    """

    email: str
    email_type: str = "Primary"  # Default to 'Primary'

    @field_validator("email")
    @classmethod
    def validate_email(cls, email):
        try:
            emailinfo = validate_email(email, check_deliverability=False)
            return emailinfo.normalized
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email format. {email}")


class CreatePhone(BaseModel):
    """
    Schema for creating a phone number.
    """

    phone_number: str
    phone_type: str | None = None

    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, phone_number_str):
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


class CreateAddress(BaseModel):
    """
    Schema for creating an address.
    """

    address_line_1: str  # Required (e.g., "123 Main St")
    address_line_2: str | None = None  # Optional (e.g., "Apt 4B", "Suite 200")
    city: str
    state: str = "NM"  # Default to New Mexico
    postal_code: str
    country: str = "US"  # Default to United States
    address_type: str | None = None  # Optional (e.g., "Primary", "Billing", "Shipping")


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

    emails: list[CreateEmail]
    phones: list[CreatePhone]
    addresses: list[CreateAddress]


# ============= EOF =============================================

#
#
# @field_validator("phone", mode="before")
# @classmethod
# def validate_phone(cls, phone_number_str):
#     region = "US"
#     try:
#         parsed_number = phonenumbers.parse(phone_number_str, region)
#         if phonenumbers.is_valid_number(parsed_number):
#             # You can also format the number if needed
#             formatted_number = phonenumbers.format_number(
#                 parsed_number, phonenumbers.PhoneNumberFormat.E164
#             )
#             return formatted_number
#         else:
#             raise ValueError(f"Invalid phone number. {phone_number_str}")
#     except NumberParseException as e:
#         raise ValueError(f"Invalid phone number. {phone_number_str}")
#
# @field_validator("email")
# @classmethod
# def validate_email(cls, email):
#     # try:
#     # Check that the email address is valid. Turn on check_deliverability
#     # for first-time validations like on account creation pages (but not
#     # login pages).
#     emailinfo = validate_email(email, check_deliverability=False)
#
#     # After this point, use only the normalized form of the email address,
#     # especially before going to a database query.
#     email = emailinfo.normalized
#     return email
#     # except EmailNotValidError as e:
#     # if v is not None:
#     #     # Basic email validation
#     #     if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", v):
#     #         raise ValueError(f"Invalid email format. {v}")
#     # return v
