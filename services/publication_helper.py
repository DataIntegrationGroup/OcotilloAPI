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
from db.publication import Author, Publication, PublicationAuthorAssociation
from schemas.create.publication import CreatePublication
from sqlalchemy.orm import Session
from sqlalchemy import select


def add_publication(session: Session, publication_data: CreatePublication):

    publication_data = publication_data.model_dump()
    authors = publication_data.pop('authors', [])

    associations = []
    with session.no_autoflush:
        for i,a in enumerate(authors):
            if isinstance(a, str):
                sql = select(Author).where(Author.name == a)
                dbauthor = session.scalars(sql).first()
                print('asdf', a, dbauthor)
                if dbauthor is None:
                    dbauthor = Author(name=a)
                    session.add(dbauthor)
                    # session.commit()
                    # session.refresh(dbauthor)
            elif isinstance(a, int):
                dbauthor = session.get(Author, a)

            assoc = PublicationAuthorAssociation(author=dbauthor, author_order=i)
            associations.append(assoc)
        # print('dbauthors', dbauthors)

        publication = Publication(**publication_data)
        session.add(publication)
        publication.author_associations=associations

        session.commit()
        return publication

# ============= EOF =============================================
