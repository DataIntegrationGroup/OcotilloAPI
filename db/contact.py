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
from sqlalchemy import Integer, ForeignKey, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy_utils import TSVectorType
from typing import List

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term


class ThingContactAssociation(Base, AutoBaseMixin):
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )

    contact: Mapped[List["Contact"]] = relationship("Contact")
    thing: Mapped[List["Thing"]] = relationship("Thing")  # noqa: F821


class Contact(Base, AutoBaseMixin, ReleaseMixin):
    name: Mapped[str | None] = mapped_column(String(100))
    organization: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = lexicon_term()
    contact_type: Mapped[str] = lexicon_term()
    nma_pk_owners: Mapped[str | None] = mapped_column(String(100))

    phones: Mapped[List["Phone"]] = relationship(
        "Phone", back_populates="contact", passive_deletes=True
    )
    emails: Mapped[List["Email"]] = relationship(
        "Email", back_populates="contact", passive_deletes=True
    )
    addresses: Mapped[List["Address"]] = relationship(
        "Address", back_populates="contact", passive_deletes=True
    )

    search_vector: Mapped[TSVectorType] = mapped_column(
        TSVectorType("name", "role", "organization", "nma_pk_owners")
    )

    author_associations: Mapped[List["AuthorContactAssociation"]] = (  # noqa: F821
        relationship(
            "AuthorContactAssociation",
            back_populates="contact",
            cascade="all, delete-orphan",
        )
    )
    authors = association_proxy("author_associations", "author")
    thing_associations: Mapped[List["ThingContactAssociation"]] = relationship(
        "ThingContactAssociation",
        back_populates="contact",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    things = association_proxy("thing_associations", "thing")


class Phone(Base, AutoBaseMixin, ReleaseMixin):
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_type: Mapped[str] = lexicon_term(nullable=False)

    contact: Mapped["Contact"] = relationship(
        "Contact", back_populates="phones", passive_deletes=True
    )
    search_vector: Mapped[TSVectorType] = mapped_column(TSVectorType("phone_number"))


class Email(Base, AutoBaseMixin, ReleaseMixin):
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    email_type: Mapped[str] = lexicon_term(nullable=False)

    contact: Mapped["Contact"] = relationship(
        "Contact", back_populates="emails", passive_deletes=True
    )

    search_vector: Mapped[TSVectorType] = mapped_column(TSVectorType("email"))


class Address(Base, AutoBaseMixin, ReleaseMixin):
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = lexicon_term(nullable=False, default="United States")
    address_type: Mapped[str] = lexicon_term(nullable=False)

    contact: Mapped["Contact"] = relationship(
        "Contact", back_populates="addresses", passive_deletes=True
    )
    search_vector: Mapped[TSVectorType] = mapped_column(
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
