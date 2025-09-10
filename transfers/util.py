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
import re
from pathlib import Path
import logging
import httpx
import pyproj
from shapely import Point
from shapely.ops import transform

from sqlalchemy.orm import Session
import pandas as pd

from db import Thing, Location

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("transfers/transfer.log", mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

TRANSFORMERS = {}


def read_csv(name: str) -> pd.DataFrame:
    p = Path(".") / "transfers" / "data" / name
    return pd.read_csv(p)


def transform_srid(geometry, source_srid, target_srid):
    """
    geometry must be a shapely geometry object, like Point, Polygon, or MultiPolygon
    """
    transformer_key = (source_srid, target_srid)
    if transformer_key not in TRANSFORMERS:
        source_crs = pyproj.CRS(f"EPSG:{source_srid}")
        target_crs = pyproj.CRS(f"EPSG:{target_srid}")
        transformer = pyproj.Transformer.from_crs(
            source_crs, target_crs, always_xy=True
        )
        TRANSFORMERS[transformer_key] = transformer
    else:
        transformer = TRANSFORMERS[transformer_key]
    return transform(transformer.transform, geometry)


def get_valid_point_ids(session, thing_type="water well"):
    things = get_valid_things(session, thing_type)
    valid_pointids = [thing.name for thing in things]
    return valid_pointids


def get_valid_things(session, thing_type="water well"):
    return session.query(Thing).where(Thing.thing_type == thing_type).all()


def extract_organization(alternate_id: str) -> str:
    if alternate_id.startswith("TWDB"):
        return "TWDB"
    elif alternate_id.startswith("NMED"):
        return "NMED"

    # TODO: There are a bunch of other formats used for AlternateSiteID.
    # we should try to handle as many as possible but its not the end of the world
    # if we have to update the organization for a particular alternate id at a later time
    for regex, org in ((r"^A-Z{1,2}-\d{5,6}$", "NMOSE"), (r"\d+(\.\d+){3,}", "PLSS")):

        if re.match(regex, alternate_id):
            return org

    return "Unknown"


def filter_to_valid_point_ids(session: Session, df: pd.DataFrame) -> pd.DataFrame:
    valid_point_ids = get_valid_point_ids(session)
    return df[df["PointID"].isin(valid_point_ids)]


def convert_to_wgs84_vertical_datum(row, z):
    if row.VerticalDatum == "NAVD88":
        z = z + 2.0  # TODO: check this transformation
    elif row.VerticalDatum == "NGVD29":
        z = z + 3.0  # TODO: check this transformation
    return z


def get_state_from_point(lon: float, lat: float) -> str:
    attrs = get_tiger_data(lon, lat, layer=0, outfields="BASENAME")
    return attrs["BASENAME"]


def get_county_from_point(lon: float, lat: float) -> str:
    """
    Look up county for a given longitude/latitude
    using the US Census TIGERWeb REST API.
    """

    attrs = get_tiger_data(lon, lat, layer=1, outfields="BASENAME")
    return attrs["BASENAME"]


def get_tiger_data(
    lon: float, lat: float, layer: int, outfields: str = "*"
) -> dict | None:
    url = f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/{layer}/query"
    params = {
        "f": "json",
        "where": "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": outfields,
        "returnGeometry": "false",
    }
    resp = httpx.get(url, params=params, timeout=15)
    data = resp.json()
    if not data.get("features"):
        return None

    return data["features"][0]["attributes"]


def get_quad_name_from_point(lon: float, lat: float) -> str:
    url = "https://carto.nationalmap.gov/arcgis/rest/services/map_indices/MapServer/10/query"
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CELL_NAME,CELL_MAPCODE",
        "returnGeometry": "false",
    }

    resp = httpx.get(url, params=params, timeout=15)
    logger.info(resp)
    data = resp.json()

    if data["features"]:
        attrs = data["features"][0]["attributes"]
        return attrs["CELL_NAME"]
    else:
        logger.warning(f"No quad name found for POINT ({lon} {lat})")


def get_epqs_elevation(lon: float, lat: float) -> float:
    url = "https://epqs.nationalmap.gov/v1/json"
    params = {
        "x": lon,
        "y": lat,
        "units": "Meters",
        "wkid": "4326",
        "includeDate": False,
    }

    resp = httpx.get(url, params=params)
    data = resp.json()

    return data["value"]


def make_location(row: pd.Series) -> Location:

    # TODO: should the altitude be fetched from USGS'
    # Elevation Point Query Service https://epqs.nationalmap.gov/v1/docs
    xypoint = transform_srid(
        Point(row.Easting, row.Northing),
        source_srid=26913,
        target_srid=4326,  # WGS84 SRID
    )

    z = 0

    # idx = row.index
    # idx = df.index.get_loc(row.name)
    # print('asdfa', idx, row.name)
    # if not z:
    #     z = get_epqs_elevation(xypoint.x, xypoint.y)

    # z = row.Altitude if row.Altitude else 0
    # convert z from ft to meters
    z = z * 0.3048

    point = Point(row.Easting, row.Northing, z)

    # Convert the point to a WGS84 coordinate system
    transformed_point = transform_srid(
        point, source_srid=26913, target_srid=4326  # WGS84 SRID
    )

    # TODO: Add tests for these functions. move to a different location
    # use in Location API

    # TODO: determine correct created_at value
    # created_at = row.DateCreated

    location = Location(
        # nma_pk_location=row.LocationId,
        name=row.PointID,
        point=transformed_point.wkt,
        release_status="public" if row.PublicRelease else "private",
        # elevation_accuracy=row.AltitudeAccuracy,
        # elevation_method=row.AltitudeMethod,
        # created_at=created_at,
        # point_accuracy=row.CoordinateAccuracy,
        # point_method=row.CoordinateMethod,
    )
    return location


if __name__ == "__main__":
    # quad = get_quad_name_from_point(-106.5, 34.2)
    # print(quad)
    # state = get_state_from_point(-106.5, 34.2)
    # print(state)
    # county = get_county_from_point(-106.5, 34.2)
    # print(county)
    z = get_epqs_elevation(-106.5, 34.2)
    print(z)

# ============= EOF =============================================
