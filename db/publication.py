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
from db import AutoBaseMixin, Base, AuditMixin
from sqlalchemy import Column, Integer, String, Text, Date, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy


class Publication(Base, AutoBaseMixin):

    title = Column(Text, nullable=False)
    abstract = Column(Text)
    doi = Column(String, unique=True)
    year = Column(Integer)
    # publication_type_id = Column(Integer, ForeignKey('publication_types.id'))
    publisher = Column(String)
    url = Column(String)

    publication_type = Column(
        String(100), ForeignKey("lexicon_term.term"), nullable=False
    )
    # publication_type = relationship("PublicationType")
    # authors = relationship(
    #     "Author",
    #     secondary=publication_authors,
    #     order_by=publication_authors.c.author_order,
    # )
    # topics = relationship("Topic", secondary=publication_topics)
    author_associations = relationship(
        "AuthorPublicationAssociation",
        back_populates="publication",
        cascade="all, delete-orphan",
    )
    authors = association_proxy("author_associations", "author")


class Author(Base, AutoBaseMixin):
    __tablename__ = "pub_author"
    name = Column(String, nullable=False)
    # id = Column(Integer, primary_key=True)
    # first_name = Column(String, nullable=False)
    # last_name = Column(String, nullable=False)
    # orcid = Column(String, unique=True)
    # email = Column(String)
    affiliation = Column(String)

    publication_associations = relationship(
        "AuthorPublicationAssociation",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    publications = association_proxy("publication_associations", "publication")

    contact_associations = relationship(
        "AuthorContactAssociation",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    contacts = association_proxy("author_associations", "contact")


class AuthorContactAssociation(Base, AuditMixin):
    __tablename__ = "pub_author_contact_association"
    author_id = Column(
        Integer,
        ForeignKey("pub_author.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    contact_id = Column(
        Integer,
        ForeignKey("contact.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )

    author = relationship("Author", back_populates="contact_associations")
    contact = relationship("Contact", back_populates="author_associations")


class AuthorPublicationAssociation(Base, AuditMixin):
    __tablename__ = "pub_author_publication_association"
    publication_id = Column(
        ForeignKey("publication.id", ondelete="CASCADE"), primary_key=True
    )
    author_id = Column(
        ForeignKey("pub_author.id", ondelete="CASCADE"), primary_key=True
    )
    author_order = Column(Integer, nullable=False)

    publication = relationship("Publication", back_populates="author_associations")
    author = relationship("Author", back_populates="publication_associations")


# ============= EOF =============================================
