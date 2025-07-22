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
from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from sqlalchemy_utils import TSVectorType

from db.base import Base, AutoBaseMixin, lexicon_term


class ThingContactAssociation(Base, AutoBaseMixin):
    thing_id = Column(Integer, ForeignKey("thing.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contact.id"), nullable=False)


class Contact(Base, AutoBaseMixin):
    name = Column(String(100), nullable=False)
    role = lexicon_term(nullable=False)

    phones = relationship("Phone", back_populates="contact")
    emails = relationship("Email", back_populates="contact")
    addresses = relationship("Address", back_populates="contact")
    # email = Column(String(100), nullable=True)
    # phone = Column(String(20), nullable=True)
    # owner_id = Column(Integer, ForeignKey("owner.id"), nullable=False)
    # owner = relationship("Owner")

    search_vector = Column(TSVectorType("name", "role"))

    author_associations = relationship(
        "AuthorContactAssociation",
        back_populates="contact",
        cascade="all, delete-orphan",
    )
    authors = association_proxy("author_associations", "author")
    things = relationship("Thing", secondary="thing_contact_association")


class Phone(Base, AutoBaseMixin):
    contact_id = Column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    phone_number = Column(String(20), nullable=False)
    phone_type = lexicon_term(nullable=False)

    contact = relationship("Contact", back_populates="phones")
    search_vector = Column(TSVectorType("phone_number"))


class Email(Base, AutoBaseMixin):
    contact_id = Column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    email = Column(String(100), nullable=False)
    email_type = lexicon_term(nullable=False)

    contact = relationship("Contact", back_populates="emails")

    search_vector = Column(TSVectorType("email"))


class Address(Base, AutoBaseMixin):
    contact_id = Column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    address_line_1 = Column(String(255), nullable=False)
    address_line_2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country = lexicon_term(nullable=False, default="United States")
    address_type = lexicon_term(nullable=False)

    contact = relationship("Contact", back_populates="addresses")
    search_vector = Column(
        TSVectorType(
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
        )
    )


# ============= EOF =============================================
