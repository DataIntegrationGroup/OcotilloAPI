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
from fastapi import Query, Response
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select, func
from starlette import status
from api.pagination import CustomPage
from constants import SRID_WGS84
from core.dependencies import (
    session_dependency,
    admin_dependency,
    editor_dependency,
    viewer_dependency,
)
from db.location import Location
from schemas.location import CreateLocation, LocationResponse, UpdateLocation
from services.geospatial_helper import make_within_wkt
from services.query_helper import make_query, order_sort_filter, simple_get_by_id
from services.crud_helper import model_patcher, model_deleter, model_adder

from fastapi import APIRouter

router = APIRouter(prefix="/location", tags=["location"])


@router.post(
    "",
    # response_model=GetLocation,
    summary="Create a new sample location",
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    location_data: CreateLocation, session: session_dependency, user: admin_dependency
) -> LocationResponse:
    """
    Create a new sample location in the database.
    """
    return model_adder(session, Location, location_data, user=user)


@router.patch(
    "/{location_id}",
    summary="Update a location",
)
def update_location(
    location_id: int,
    location_data: UpdateLocation,
    session: session_dependency,
    user: editor_dependency,
) -> LocationResponse:
    """
    Update a sample location in the database.
    """
    return model_patcher(session, Location, location_id, location_data, user=user)


# @router.get("/shapefile", summary="Get location as shapefile")
# async def get_location_shapefile(
#     query: str = None, session: Session = Depends(get_db_session)
# ) -> FileResponse:
#     """
#     Retrieve all sample locations as a shapefile.
#     """
#     sql = select(Location)
#     if query:
#         sql = sql.where(make_query(Location, query))
#
#     result = session.execute(sql)
#     locations = result.scalars().all()
#     # create a shapefile from the locations
#
#     create_shapefile(locations, "locations.shp")
#     # Return the shapefile as a zip (optional: zip the .shp, .shx, .dbf files)
#     import zipfile
#
#     with zipfile.ZipFile("locations.zip", "w") as zf:
#         for ext in ["shp", "shx", "dbf"]:
#             zf.write(f"locations.{ext}")
#     return FileResponse(
#         "locations.zip", media_type="application/zip", filename="locations.zip"
#     )


# @router.get("/feature_collection", summary="Get location feature collection")
# async def get_location_feature_collection(
#     query: str = None, session: Session = Depends(get_db_session)
# ) -> dict:
#     """
#     Retrieve all sample locations as a GeoJSON FeatureCollection.
#     """
#     sql = select(Location, geofunc.ST_AsGeoJSON(Location.point).label("geojson"))
#     if query:
#         sql = sql.where(make_query(Location, query))
#
#     result = session.execute(sql)
#     locations = result.all()
#
#     features = []
#     for location, geojson in locations:
#         feature = {
#             "type": "Feature",
#             "geometry": json.loads(geojson),
#         }
#         features.append(feature)
#
#     return {
#         "type": "FeatureCollection",
#         "features": features,
#     }


@router.get(
    "",
    summary="Get all locations",
)
async def get_location(
    session: session_dependency,
    user: viewer_dependency,
    nearby_point: str = None,
    nearby_distance_km: float = 1,
    within: str = None,
    query: str = None,
    sort: str = None,
    order: str = None,
    filter_: str = Query(alias="filter", default=None),
) -> CustomPage[LocationResponse]:
    """
    Retrieve all wells from the database.
    """
    sql = select(Location)

    if query:
        sql = sql.where(make_query(Location, query))
    elif nearby_point:
        nearby_point = func.ST_GeomFromText(nearby_point, SRID_WGS84)
        sql = sql.where(
            # func.ST_Distance(SampleLocation.point, nearby_point) <= nearby_distance_km
            func.ST_Distance(nearby_point, Location.point)
            <= nearby_distance_km
        )
    elif within:
        sql = make_within_wkt(sql, within)

    sql = order_sort_filter(sql, Location, sort, order, filter_)

    return paginate(query=sql, conn=session)


@router.get(
    "/{location_id}",
    summary="Get location by ID",
)
async def get_location_by_id(
    location_id: int, session: session_dependency, user: viewer_dependency
) -> LocationResponse:
    """
    Retrieve a sample location by ID from the database.
    """
    location = simple_get_by_id(session, Location, location_id)
    return location


@router.delete("/{location_id}", summary="Delete location by ID")
async def delete_location(
    location_id: int, session: session_dependency, user: admin_dependency
) -> Response:
    """
    Delete a sample location by ID from the database.
    """
    return model_deleter(session, Location, location_id)


# ============= EOF =============================================
