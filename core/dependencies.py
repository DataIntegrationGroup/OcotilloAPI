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
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from core.permissions import authenticated
from db.engine import get_db_session

session_dependency: type[Session] = Annotated[Session, Depends(get_db_session)]

"""
Developer Notes

Viewer can view all "global" entities Location, Sample, Group, Lexicon, etc

Editor can do everything Viewer can do
    + edit existing objects

Admin, can do everything Editor and Viewer can do
    + create new objects

"""

# General Purpose Authentication/Permissions -----------------------------------

admin_function = authenticated(permissions=["Admin"])
editor_function = authenticated(permissions=["Editor"])
viewer_function = authenticated(permissions=["Viewer"])


# AMP-Specific Authentication/Permissions --------------------------------------

amp_admin_function = authenticated(permissions=["AMPAdmin"])
amp_editor_function = authenticated(permissions=["AMPEditor"])
amp_viewer_function = authenticated(permissions=["AMPViewer"])


# Lexicon-Specific Authentication/Permissions ----------------------------------

lexicon_admin_function = authenticated(permissions=["LexiconAdmin"])
lexicon_editor_function = authenticated(permissions=["LexiconEditor"])


# Testing-Specific Authentication/Permissions ----------------------------------
no_permission_function = authenticated(permissions=["NoPermission"])


# Permissions Dependencies -----------------------------------------------------
admin_dependency: type[dict] = Annotated[dict, Depends(admin_function)]
editor_dependency: type[dict] = Annotated[dict, Depends(editor_function)]
viewer_dependency: type[dict] = Annotated[dict, Depends(viewer_function)]

lexicon_admin_dependency: type[dict] = Annotated[dict, Depends(lexicon_admin_function)]
lexicon_editor_dependency: type[dict] = Annotated[
    dict, Depends(lexicon_editor_function)
]

amp_admin_dependency: type[dict] = Annotated[dict, Depends(amp_admin_function)]
amp_editor_dependency: type[dict] = Annotated[dict, Depends(amp_editor_function)]
amp_viewer_dependency: type[dict] = Annotated[dict, Depends(amp_viewer_function)]

no_permission_dependency: type[dict] = Annotated[dict, Depends(no_permission_function)]


# Optional Authentication for Public Endpoints --------------------------------
from typing import Optional


def optional_viewer_function():
    """
    Optional authentication for public endpoints.
    Returns None if not authenticated, user dict if authenticated.
    """
    try:
        return viewer_function()
    except Exception:
        # Not authenticated - this is a public user
        return None


optional_viewer_dependency: type[Optional[dict]] = Annotated[
    Optional[dict], Depends(optional_viewer_function)
]

# ============= EOF =============================================
