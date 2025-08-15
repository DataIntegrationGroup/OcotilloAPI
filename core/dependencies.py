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
from typing import Annotated, Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from core.permissions import authenticated
from db.engine import get_db_session

session_dependency = Annotated[Session, Depends(get_db_session)]

# authentication functions

# Admin, can do everything Editor and Viewer can do
# + create new objects
admin_function = authenticated(permissions=["Admin"])

# Editor can do everything Viewer can do
# + edit existing objects
editor_function = authenticated(permissions=["Editor"])

# Viewer can view all "global" entities Location, Sample, Group, Lexicon, etc
viewer_function = authenticated(permissions=["Viewer"])

# AMP specific permissions
amp_admin_function = authenticated(permissions=["AMPAdmin"])
amp_editor_function = authenticated(permissions=["AMPEditor"])
amp_viewer_function = authenticated(permissions=["AMPViewer"])

# for testing
no_permission_function = authenticated(permissions=["NoPermission"])


# permissions dependencies
admin_dependency = Annotated[Callable, Depends(admin_function)]
editor_dependency = Annotated[Callable, Depends(editor_function)]
viewer_dependency = Annotated[Callable, Depends(viewer_function)]


amp_admin_dependency = Annotated[Callable, Depends(amp_admin_function)]
amp_editor_dependency = Annotated[Callable, Depends(amp_editor_function)]
amp_viewer_dependency = Annotated[Callable, Depends(amp_viewer_function)]

no_permission_dependency = Annotated[Callable, Depends(no_permission_function)]
# ============= EOF =============================================
