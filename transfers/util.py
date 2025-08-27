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

import pyproj
from shapely import Point
from shapely.ops import transform
from sqlalchemy.engine import row

from sqlalchemy.orm import Session
import pandas as pd

from db import Thing, Location

TRANSFORMERS = {}


def read_csv(name: str) -> pd.DataFrame:
    p = Path(".") / "data" / name
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


def get_valid_point_ids(session):
    things = session.query(Thing).where(Thing.thing_type == "water well").all()
    valid_pointids = [thing.name for thing in things]
    return valid_pointids


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


def log(row, msg):
    print(f"{row.PointID} {msg}")


def convert_to_wgs84_vertical_datum(row, z):
    if row.VerticalDatum == "NAVD88":
        z = z + 2.0 # TODO: check this transformation
    elif row.VerticalDatum == "NGVD29":
        z = z + 3.0 # TODO: check this transformation
    return z


def make_location(row)->Location:
    z = row.Altitude if row.Altitude else 0
    # convert to WGS84 vertical datum
    z = convert_to_wgs84_vertical_datum(row, z)
    # convert z from ft to meters
    z = z * 0.3048

    point = Point(row.Easting, row.Northing, z)

    # Convert the point to a WGS84 coordinate system
    transformed_point = transform_srid(
        point, source_srid=26913, target_srid=4326  # WGS84 SRID
    )

    state = "Unknown"
    county = "Unknown"
    quad_name = "Unknown"

    # TODO: make these functions. Include them in the Location API
    # state = get_state_from_point(transformed_point)
    # county = get_county_from_point(transformed_point)
    # quad_name = get_quad_name_from_point(transformed_point)

    # TODO: determine correct created_at value
    created_at = row.DateCreated

    location = Location(
        name=row.PointID,
        point=transformed_point.wkt,
        release_status="public" if row.PublicRelease else "private",
        elevation_accuracy=row.AltitudeAccuracy,
        elevation_method=row.AltitudeMethod,

        nma_pk_location=row.LocationId,
        created_at=created_at,

        point_accuracy=row.CoordinateAccuracy,
        point_method=row.CoordinateMethod,

        state = state,
        county= county,
        quad_name= quad_name
    )
    return location


# ============= EOF =============================================
