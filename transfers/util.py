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
from pathlib import Path
import logging
from shapely import Point


from sqlalchemy.orm import Session
import pandas as pd

from db import Thing, Location
from services.util import transform_srid, get_epqs_elevation

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


def read_csv(name: str) -> pd.DataFrame:
    p = Path(".") / "transfers" / "data" / name
    return pd.read_csv(p)


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
        nma_pk_location=row.LocationId,
        # TODO: determine if PointID should map to location.name or thing.name or if the Location table needs a name field at all.
        name=row.PointID,
        point=transformed_point.wkt,
        release_status="public" if row.PublicRelease else "private",
        elevation_accuracy=row.AltitudeAccuracy,
        elevation_method=row.AltitudeMethod,
        # created_at=created_at,
        coordinate_accuracy=row.CoordinateAccuracy,
        coordinate_method=row.CoordinateMethod,
        nma_coordinate_notes=row.CoordinateNotes,
        nma_notes_location=row.LocationNotes,
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
