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
from fastapi import APIRouter
from sqlalchemy import select

from core.dependencies import viewer_dependency, session_dependency
from db.publication import Author
from schemas.publication import PublicationResponse

router = APIRouter(
    prefix="/author",
    tags=["author"],
)


@router.get(
    "/{author_id}/publications",
    response_model=list[PublicationResponse],
)
def get_author_publications(
    user: viewer_dependency, author_id: int, session: session_dependency
):
    """
    Retrieve all publications for a specific author.
    """
    sql = select(Author).where(Author.id == author_id)
    author = session.scalars(sql).first()
    return author.publications


#
# @router.post(
#     "/author", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED
# )
# async def post_publication(
#     publication_data: CreatePublication,  # Replace with your actual schema
#     session: Session = Depends(
#         get_db_session
#     ),  # Assuming get_db is defined in dependencies.py
# ):
#     """
#     Add a new publication.
#     """
#     return add_publication(session, publication_data)
#
#     # return adder(session, Publication, publication_data)


# ============= EOF =============================================
