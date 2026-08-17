# ===============================================================================
# Copyright 2023 Jake Ross
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
from starlette.responses import Response

from core.app import in_public_schema
from core.dependencies import session_dependency
from services.ngwmn_helper import (
    make_waterlevels_response,
    make_well_construction_response,
    make_lithology_response,
)

router = APIRouter(prefix="/ngwmn", tags=["NGWMN"])

# These three routes are intentionally anonymous: the federal NGWMN harvester
# polls them without credentials. @in_public_schema documents that (and lists
# them in /openapi.json) so tests/test_authorization.py can tell an intentional
# public route from an endpoint that simply forgot its `user:` dependency.


@in_public_schema
@router.get(
    "/waterlevels/{pointid}",
    summary="Get waterlevels for a given pointid in the NGWMN format",
)
def read_ngwmn_waterlevels(pointid: str, db: session_dependency):
    data = make_waterlevels_response(pointid, db)
    return Response(content=data, media_type="application/xml")


@in_public_schema
@router.get(
    "/wellconstruction/{pointid}",
    summary="Get wellconstruction for a given pointid in the NGWMN format",
)
def read_ngwmn_wellconstruction(pointid: str, db: session_dependency):
    data = make_well_construction_response(pointid, db)
    return Response(content=data, media_type="application/xml")


@in_public_schema
@router.get(
    "/lithology/{pointid}",
    summary="Get lithology for a given pointid in the NGWMN format",
)
def read_ngwmn_lithology(pointid: str, db: session_dependency):
    data = make_lithology_response(pointid, db)
    return Response(content=data, media_type="application/xml")


# ============= EOF =============================================
