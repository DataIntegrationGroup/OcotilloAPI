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
from typing import Annotated, List, Union

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

# from starlette.responses import FileResponse

from core.dependencies import session_dependency
from schemas_v2.thing import FeatureCollectionResponse
from services.geospatial_helper import create_shapefile, get_thing_features

router = APIRouter(prefix="/geospatial", tags=["geospatial"])


@router.get("")
async def get_geospatial(
    session: session_dependency,
    thing_type: Annotated[List[str], Query(title="thing_type")] = None,
    group: Annotated[
        str | int, Query(title="group")
    ] = None,
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


def get_feature_collection(
    session: session_dependency,
    thing_type: List[str] | None = None,
    group: Annotated[
        str | int, Query(title="group", description="group", alias="group")
    ] = None,
) -> FeatureCollectionResponse:
    """
    Endpoint to retrieve a GeoJSON FeatureCollection.
    """

    things = get_thing_features(session, thing_type, group)

    def make_feature_dict(thing, geometry, *other):
        return {
            "type": "Feature",
            "properties": {
                "id": thing.id,
                "thing_type": thing.thing_type,
                "name": thing.name,
                "group": group,
            },
            "geometry": json.loads(geometry),
        }

    features = [make_feature_dict(*item) for item in things]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_location_shapefile(
    session: session_dependency,
    thing_type: str | None = None,
    group: str | int | None = None,
) -> FileResponse:
    """
    Retrieve all sample locations as a shapefile.
    """

    things = get_thing_features(session, thing_type, group)
    create_shapefile(things, "things.shp")

    # Return the shapefile as a zip (optional: zip the .shp, .shx, .dbf files)
    import zipfile

    with zipfile.ZipFile("things.zip", "w") as zf:
        for ext in ["shp", "shx", "dbf"]:
            zf.write(f"things.{ext}")
    return FileResponse(
        "things.zip", media_type="application/zip", filename="things.zip"
    )


# ============= EOF =============================================
