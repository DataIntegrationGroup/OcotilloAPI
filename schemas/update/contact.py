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
from typing import Optional, Annotated

from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined


class UpdateContact(BaseModel):
    """
    Schema for updating contact information.
    """
    name: Optional[str] = None
    # thing_id: int | None = None
    # email: str | None = None
    # phone: str | None = None
    # address: str | None = None

class UpdateEmail(BaseModel):
    """
    Schema for updating email information.
    """
    # email: Annotated[Optional[str], None]
    # email_type: Annotated[Optional[str], None]
    email: Optional[str] = None# None
    email_type: Optional[str]= None# None

class UpdatePhone(BaseModel):
    """
    Schema for updating phone information.
    """
    phone_number: Optional[str] = None
    phone_type: Optional[str] = None


class UpdateAddress(BaseModel):
    """
    Schema for updating address information.
    """
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address_type: Optional[str] = None
# ============= EOF =============================================
