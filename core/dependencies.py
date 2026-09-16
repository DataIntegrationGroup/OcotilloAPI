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
from typing import Annotated, TypeAlias

from fastapi import Depends
from sqlalchemy.orm import Session

from core.permissions import authenticated, INTERNAL_OGC_GROUP
from db.engine import get_db_session

session_dependency: TypeAlias = Annotated[Session, Depends(get_db_session)]

"""
Developer Notes

Viewer can view all "global" entities Location, Sample, Group, Lexicon, etc

Editor can do everything Viewer can do
    + edit existing objects

Admin, can do everything Editor and Viewer can do
    + create new objects

That hierarchy is enforced here, by `any_of=` group lists rather than by
Authentik group membership overlap: an Admin-only account satisfies an
editor- or viewer-gated route because "Admin" appears in those lists. Before
this was explicit, `authenticated(permissions=["Viewer"])` required the
literal Viewer group, so the hierarchy held only as long as whoever
provisioned the Authentik groups granted all three tiers to every admin.

The three families below are deliberately orthogonal -- general `Admin` does
not confer `AMPAdmin` or `Lexicon.Admin`. Only tiers *within* a family nest.
"""

# General Purpose Authentication/Permissions -----------------------------------

admin_function = authenticated(any_of=["Admin"])
editor_function = authenticated(any_of=["Admin", "Editor"])
viewer_function = authenticated(any_of=["Admin", "Editor", "Viewer"])


# AMP-Specific Authentication/Permissions --------------------------------------

amp_admin_function = authenticated(any_of=["AMPAdmin"])
amp_editor_function = authenticated(any_of=["AMPAdmin", "AMPEditor"])
amp_viewer_function = authenticated(any_of=["AMPAdmin", "AMPEditor", "AMPViewer"])


# Hydrograph-Corrector Staging Permissions -------------------------------------
# The hydrograph corrector's publish and range-delete routes write and destroy
# transducer records, and the workbench driving them is still being validated
# against real logger files. `AMP.Staging` is its own group with no tier below
# it and no AMP tier above it -- an AMPAdmin does not satisfy it. Nobody holds
# it until it is granted in Authentik, so the routes ship dark and reachable
# only by whoever is testing them.
#
# This is deliberately not a fourth rung on the AMP ladder. When the workbench
# is trusted, these routes move to `amp_admin_dependency` and the group goes
# away; leaving it as a tier would make that a schema change instead of a
# one-line edit.
amp_staging_function = authenticated(any_of=["AMP.Staging"])


# Lexicon-Specific Authentication/Permissions ----------------------------------

lexicon_admin_function = authenticated(any_of=["Lexicon.Admin"])
lexicon_editor_function = authenticated(any_of=["Lexicon.Admin", "Lexicon.Editor"])


# OGC-Internal Authentication/Permissions --------------------------------------
# INTERNAL_OGC_GROUP ("OGC.Internal") still lives in core/permissions.py, where
# core/internal_ogc_auth.py's ASGI middleware reads it -- that middleware gates
# the /ogcapi-internal mount outside FastAPI's Depends() machinery. This is the
# Depends()-shaped view of the same group, for the API key routes.
#
# The key routes are gated on this group and not on a general role on purpose.
# An API key is a pre-authorized stand-in for OGC.Internal: it reaches the
# unfiltered, draft-inclusive internal collections. Minting one is therefore
# exactly as privileged as holding the group, and gating creation on, say,
# viewer_dependency would let any Viewer issue themselves that access with a
# button. See docs/api-key-management.md.
internal_ogc_function = authenticated(any_of=[INTERNAL_OGC_GROUP])


# Testing-Specific Authentication/Permissions ----------------------------------
# A group nobody is ever granted, so this dependency always 403s. Used to
# assert that group enforcement is actually wired up.
no_permission_function = authenticated(any_of=["NoPermission"])


# Permissions Dependencies -----------------------------------------------------
admin_dependency: TypeAlias = Annotated[dict, Depends(admin_function)]
editor_dependency: TypeAlias = Annotated[dict, Depends(editor_function)]
viewer_dependency: TypeAlias = Annotated[dict, Depends(viewer_function)]

lexicon_admin_dependency: TypeAlias = Annotated[dict, Depends(lexicon_admin_function)]
lexicon_editor_dependency: TypeAlias = Annotated[dict, Depends(lexicon_editor_function)]

amp_admin_dependency: TypeAlias = Annotated[dict, Depends(amp_admin_function)]
amp_editor_dependency: TypeAlias = Annotated[dict, Depends(amp_editor_function)]
amp_viewer_dependency: TypeAlias = Annotated[dict, Depends(amp_viewer_function)]

amp_staging_dependency: TypeAlias = Annotated[dict, Depends(amp_staging_function)]

internal_ogc_dependency: TypeAlias = Annotated[dict, Depends(internal_ogc_function)]

no_permission_dependency: TypeAlias = Annotated[dict, Depends(no_permission_function)]
# ============= EOF =============================================
