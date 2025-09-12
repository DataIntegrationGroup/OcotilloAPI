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
from datetime import datetime
import re
import io
import logging
import httpx
import pyproj
from shapely import Point
from shapely.ops import transform

from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from db import Thing, Location
from services.gcs_helper import get_storage_bucket

import sys


class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ""

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


log_filename = f"transfers/transfer_{datetime.now():%Y-%m-%dT%Hh%Mm%Ss}.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# redirect stderr to the logger
sys.stderr = StreamToLogger(logger, logging.ERROR)

TRANSFORMERS = {}


def replace_nans(df: pd.DataFrame, default=None) -> pd.DataFrame:
    df = df.replace(pd.NA, default)
    return df.replace({np.nan: default})


def read_csv(name: str, dtype: dict | None = None) -> pd.DataFrame:
    bucket = get_storage_bucket()
    blob = bucket.blob(f"nma_csv/{name}.csv")
    data = blob.download_as_bytes()

    if dtype:
        return pd.read_csv(io.BytesIO(data), dtype=dtype)
    else:
        return pd.read_csv(io.BytesIO(data))


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
    name = row.PointID

    location = Location(
        nma_pk_location=row.LocationId,
        # TODO: determine if PointID should map to location.name or thing.name or if the Location table needs a name field at all.
        name=row.PointID,
        point=transformed_point.wkt,
        release_status="public" if row.PublicRelease else "private",
        elevation_accuracy=row.AltitudeAccuracy,
        # TODO: map code to meaning since meaning is used as the lexicon term
        # elevation_method=row.AltitudeMethod,
        # created_at=created_at,
        # TODO: row.CoordinateAccuracy is not a float
        # coordinate_accuracy=row.CoordinateAccuracy,
        # TODO: map code to meaning since meaning is used as the lexicon term
        # coordinate_method=row.CoordinateMethod,
        nma_coordinate_notes=row.CoordinateNotes,
        nma_notes_location=row.LocationNotes,
    )
    return location


def make_lu_to_lexicon_mapper():
    lu_tables = [
        # "LU_AltitudeDatum",     # the code is the value, so no need for mapping
        "LU_AltitudeMethod",  # CODE/MEANING
        "LU_CollectionMethod",  # CODE/MEANING
        "LU_ConstructionMethod",  # CODE/MEANING
        "LU_CoordinateAccuracy",  # CODE/MEANING
        # "LU_CoordinateDatum",   # the code is the value, so no need for mapping
        "LU_CoordinateMethod",  # CODE/MEANING
        "LU_CurrentUse",  # CODE/MEANING
        "LU_DataQuality",  # CODE/MEANING
        "LU_DataSource",  # CODE/MEANING
        "LU_Depth_CompletionSource",  # CODE/MEANING
        "LU_Discharge_ChemistrySource",  # CODE/MEANING
        # "LU_FieldNoteTypes",    # not being used in the transfers since there are no records
        # "LU_Formations",        # needs to be cleaned before it can be used
        "LU_LevelStatus",  # CODE/MEANING
        # "LU_Lithology",         # needs to be cleaned before it can be used
        "LU_MajorAnalyte",  # CODE/MEANING
        "LU_MeasurementMethod",  # CODE/MEANING
        # "LU_MeasuringAgency",   # the abreviation is what is used in the new schema
        "LU_MinorTraceAnalyte",  # CODE/MEANING
        "LU_MonitoringStatus",  # CODE/MEANING
        "LU_SampleType",  # CODE/MEANING
        "LU_SiteType",  # CODE/MEANING
        "LU_Status",  # CODE/MEANING
    ]

    mappers = {}

    for lu_table in lu_tables:
        table = read_csv(lu_table)

        for i, row in table.iterrows():
            if lu_table == "LU_Formations":
                code = row.Code
                meaning = row.Meaning
            else:
                code = row.CODE
                meaning = row.MEANING

            mappers.update({f"{lu_table}:{code}": meaning})
    return mappers


lu_to_lexicon_map = make_lu_to_lexicon_mapper()


if __name__ == "__main__":
    print(lu_to_lexicon_map)

# ============= EOF =============================================
