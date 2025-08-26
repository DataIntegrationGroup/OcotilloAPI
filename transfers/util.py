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

import pyproj
from shapely import Point
from shapely.ops import transform

from sqlalchemy.orm import Session
import pandas as pd

from db import Thing, Location

TRANSFORMERS = {}


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
    things = session.query(Thing).where(Thing.thing_type=='water well').all()
    valid_pointids = [thing.name for thing in things]
    return valid_pointids


def extract_organization(alternate_id: str) -> str:
    if alternate_id.startswith("TWDB"):
        return "TWDB"
    elif alternate_id.startswith("NMED"):
        return "NMED"

    for regex, org in ((r'^A-Z{1,2}-\d{5,6}$', 'NMOSE'),
                       (r'\d+(\.\d+){3,}', 'PLSS')):

        if re.match(regex, alternate_id):
            return org

    return "Unknown"


def filter_to_valid_point_ids(session: Session, df: pd.DataFrame) -> pd.DataFrame:
    valid_point_ids = get_valid_point_ids(session)
    return df[df["PointID"].isin(valid_point_ids)]

def log(row, msg):
    print(f"{row.PointID} {msg}")


def make_location(row):
    point = Point(row.Easting, row.Northing)
    transformed_point = transform_srid(
        point, source_srid=26913, target_srid=4326  # WGS84 SRID
    )

    return Location(
        name=row.PointID,
        point=transformed_point.wkt,
        release_status="public" if row.PublicRelease else "private",
        # visible=row_dict["PublicRelease"],
    )

# ============= EOF =============================================
