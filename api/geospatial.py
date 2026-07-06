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
import json
import os
import shutil
import tempfile
from typing import Annotated, List

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from geoalchemy2.shape import to_shape
from shapely.io import to_geojson
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from core.dependencies import session_dependency, viewer_dependency
from db import Group
from schemas.thing import FeatureCollectionResponse
from services.geospatial_helper import create_shapefile, get_thing_features
from services.query_helper import simple_get_by_id

router = APIRouter(prefix="/geospatial", tags=["geospatial"])


@router.get("")
def get_geospatial(
    user: viewer_dependency,
    session: session_dependency,
    thing_type: Annotated[List[str], Query(title="thing_type")] = None,
    group: Annotated[str | int, Query(title="group")] = None,
    format_: Annotated[
        str,
        Query(
            title="format",
            description="Format of the response. 'geojson' for GeoJSON FeatureCollection, 'shapefile' for a shapefile.",
            alias="format",
            pattern="^(geojson|shapefile)$",
        ),
    ] = "geojson",
):
    """
    Endpoint to retrieve a GeoJSON FeatureCollection or a shapefile.
    If the request is for a shapefile, it will return a zip file containing the shapefile.
    Otherwise, it returns a GeoJSON FeatureCollection.
    """

    if format_ == "geojson":
        return get_feature_collection(session, thing_type, group)
    else:
        return get_location_shapefile(session, thing_type, group)


@router.get("/project-area/{group_id}", summary="Get project area for group")
def get_project_area(
    user: viewer_dependency, session: session_dependency, group_id: int
) -> FeatureCollectionResponse:

    group = simple_get_by_id(session, Group, group_id)

    if not group.project_area:
        raise HTTPException(status_code=404, detail="Group has no project area")

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(to_geojson(to_shape(group.project_area))),
            "properties": {
                "group_id": group.id,
                "group_name": group.name,
                "group_description": group.description,
            },
        }
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_feature_collection(
    session: session_dependency,
    thing_type: List[str] | None = None,
    group: Annotated[
        str | int, Query(title="group", description="group", alias="group")
    ] = None,
) -> StreamingResponse:
    """
    Retrieve a GeoJSON FeatureCollection.

    Streamed feature-by-feature so the entire result set is never buffered in
    memory at once.
    """

    things = get_thing_features(session, thing_type, group)

    def make_feature_dict(thing, geometry, elevation, *other):
        geometry = json.loads(geometry)
        geometry["coordinates"].append(elevation)
        return {
            "type": "Feature",
            "properties": {
                "id": thing.id,
                "thing_type": thing.thing_type,
                "name": thing.name,
                "group": group,
            },
            "geometry": geometry,
        }

    def generate():
        yield '{"type": "FeatureCollection", "features": ['
        first = True
        for item in things:
            yield ("" if first else ",") + json.dumps(make_feature_dict(*item))
            first = False
        yield "]}"

    return StreamingResponse(generate(), media_type="application/geo+json")


def get_location_shapefile(
    session: session_dependency,
    thing_type: str | None = None,
    group: str | int | None = None,
) -> FileResponse:
    """
    Retrieve all sample locations as a shapefile.
    """

    things = get_thing_features(session, thing_type, group)

    # Write into a temp dir: the App Engine app directory is read-only, and /tmp
    # is RAM-backed, so build here and clean up after the response is sent.
    tmpdir = tempfile.mkdtemp()
    shp_path = os.path.join(tmpdir, "things.shp")
    zip_path = os.path.join(tmpdir, "things.zip")

    create_shapefile(things, shp_path)

    import zipfile

    with zipfile.ZipFile(zip_path, "w") as zf:
        for ext in ["shp", "shx", "dbf"]:
            zf.write(os.path.join(tmpdir, f"things.{ext}"), arcname=f"things.{ext}")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="things.zip",
        background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
    )


# ============= EOF =============================================
