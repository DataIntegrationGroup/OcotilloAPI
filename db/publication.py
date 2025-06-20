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
from db import AutoBaseMixin
from sqlalchemy import (
    Column, Integer, String, Text, Date, ForeignKey, Table, DateTime
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

# Association tables
publication_authors = Table(
    'publication_authors', Base.metadata,
    Column('publication_id', ForeignKey('publication.id'), primary_key=True),
    Column('author_id', ForeignKey('author.id'), primary_key=True),
    Column('author_order', Integer, nullable=False)
)

# publication_topics = Table(
#     'publication_topics', Base.metadata,
#     Column('publication_id', ForeignKey('publications.id'), primary_key=True),
#     Column('topic_id', ForeignKey('topics.id'), primary_key=True)
# )

# class PublicationType(Base, AutoBaseMixin):
#     name = Column(String, unique=True, nullable=False)


class Publication(Base):
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    doi = Column(String, unique=True)
    publication_date = Column(Date)
    # publication_type_id = Column(Integer, ForeignKey('publication_types.id'))
    publisher = Column(String)
    url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    publication_type = Column(String(100), ForeignKey('lexicon_term.term'), nullable=False)
    # publication_type = relationship("PublicationType")
    authors = relationship("Author", secondary=publication_authors, order_by=publication_authors.c.author_order)
    # topics = relationship("Topic", secondary=publication_topics)

class Author(Base, AutoBaseMixin):
    __tablename__ = 'pub_author'
    # id = Column(Integer, primary_key=True)
    # first_name = Column(String, nullable=False)
    # last_name = Column(String, nullable=False)
    # orcid = Column(String, unique=True)
    # email = Column(String)
    affiliation = Column(String)


class AuthorContactAssociation(Base, AutoBaseMixin):
    __tablename__ = 'pub_author_contact_association'
    author_id = Column(Integer, ForeignKey('author.id'), nullable=False)
    contact_id = Column(Integer, ForeignKey('contact.id'), nullable=False)



# class Topic(Base):
#     __tablename__ = 'topics'
#     id = Column(Integer, primary_key=True)
#     name = Column(String, unique=True, nullable=False)

# ============= EOF =============================================
