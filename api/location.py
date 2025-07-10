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
from typing import Union

from fastapi import Depends
from fastapi_pagination.ext.sqlalchemy import paginate
from geoalchemy2 import functions as geofunc
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import FileResponse
from api.pagination import CustomPage
from constants import SRID_WGS84
from db import adder, Location, WellThing
from db.engine import get_db_session
from schemas.base_get import GetLocation
from schemas.create.location import CreateLocation
from schemas.response.location import LocationResponse
from schemas.response.well import LocationWellResponse
from services.geospatial_helper import create_shapefile, make_within_wkt
from services.query_helper import make_query


from fastapi import APIRouter

router = APIRouter(prefix="/location", tags=["location"])


@router.post(
    "/",
    # response_model=GetLocation,
    summary="Create a new sample location",
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    location_data: CreateLocation, session: Session = Depends(get_db_session)
) -> LocationResponse:
    """
    Create a new sample location in the database.
    """
    return adder(session, Location, location_data)


@router.get("/shapefile", summary="Get location as shapefile")
async def get_location_shapefile(
    query: str = None, session: Session = Depends(get_db_session)
) -> FileResponse:
    """
    Retrieve all sample locations as a shapefile.
    """
    sql = select(Location)
    if query:
        sql = sql.where(make_query(Location, query))

    result = session.execute(sql)
    locations = result.scalars().all()
    # create a shapefile from the locations

    create_shapefile(locations, "locations.shp")
    # Return the shapefile as a zip (optional: zip the .shp, .shx, .dbf files)
    import zipfile

    with zipfile.ZipFile("locations.zip", "w") as zf:
        for ext in ["shp", "shx", "dbf"]:
            zf.write(f"locations.{ext}")
    return FileResponse(
        "locations.zip", media_type="application/zip", filename="locations.zip"
    )


@router.get("/feature_collection", summary="Get location feature collection")
async def get_location_feature_collection(
    query: str = None, session: Session = Depends(get_db_session)
) -> dict:
    """
    Retrieve all sample locations as a GeoJSON FeatureCollection.
    """
    sql = select(Location, geofunc.ST_AsGeoJSON(Location.point).label("geojson"))
    if query:
        sql = sql.where(make_query(Location, query))

    result = session.execute(sql)
    locations = result.all()

    features = []
    for location, geojson in locations:
        feature = {
            "type": "Feature",
            "geometry": geojson,
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get(
    "/",
    summary="Get all locations",
)
async def get_location(
    nearby_point: str = None,
    nearby_distance_km: float = 1,
    within: str = None,
    query: str = None,
    expand: str = None,
    session: Session = Depends(get_db_session),
) -> CustomPage[Union[LocationResponse, LocationWellResponse]]:
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

    if expand == "well":
        sql = sql.outerjoin(WellThing)

    def transformer(items):
        if expand == "well":
            return [LocationWellResponse.model_validate(item) for item in items]
        return [LocationResponse.model_validate(item) for item in items]

    return paginate(query=sql, conn=session, transformer=transformer)


@router.get(
    "/{location_id}",
    summary="Get location by ID",
)
async def get_location_by_id(
    location_id: int, expand: str = None, session: Session = Depends(get_db_session)
) -> LocationResponse | LocationWellResponse:
    """
    Retrieve a sample location by ID from the database.
    """
    sql = select(Location).where(Location.id == location_id)

    result = session.execute(sql)
    location = result.scalar_one_or_none()

    if not location:
        return {"message": "Location not found"}

    response_klass = LocationResponse
    if expand == "well":
        response_klass = LocationWellResponse

    return response_klass.model_validate(location)


# ============= EOF =============================================
