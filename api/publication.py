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
from db import get_db_session, adder
from db.publication import Publication
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.create.publication import CreatePublication
from schemas.response.publication import PublicationResponse
from services.publication_helper import add_publication
from sqlalchemy.orm import Session


router = APIRouter(
    prefix="/publication",
    tags=["publication"],
)


@router.post(
    "/add", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED
)
async def post_publication(
    publication_data: CreatePublication,  # Replace with your actual schema
    session: Session = Depends(
        get_db_session
    ),  # Assuming get_db is defined in dependencies.py
):
    """
    Add a new publication.
    """
    return add_publication(session, publication_data)

    # return adder(session, Publication, publication_data)


# ============= EOF =============================================
