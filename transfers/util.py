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
import csv
from datetime import datetime, timezone, timedelta
import pytz
import re
import io
import logging
from shapely import Point


from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from constants import SRID_WGS84, SRID_UTM_ZONE_13N
from db import Thing, Location
from services.gcs_helper import get_storage_bucket
from services.util import (
    transform_srid,
    get_epqs_elevation_from_point,
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
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


# todo: setup of logging should be moved to function
log_filename = f"transfer_{datetime.now():%Y-%m-%dT%Hh%Mm%Ss}.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, mode="w", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# workaround to not redirect httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# redirect stderr to the logger
sys.stderr = StreamToLogger(logger, logging.ERROR)


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


def filter_by_welldata_datasource(df: pd.DataFrame) -> pd.DataFrame:
    with open('data/valid_welldata_datasources.csv', 'r') as f:
        reader = csv.reader(f)
        _ = next(reader)
        valid_datasources = [row[0] for row in reader if row[1]=='Yes']
        logger.info(f'Valid WellData Datasources: {valid_datasources}')

    return df[df["DataSource"].isin(valid_datasources)]


def filter_by_valid_measuring_agency(df: pd.DataFrame) -> pd.DataFrame:
    with open('data/valid_measuring_agency.csv', 'r') as f:
        reader = csv.reader(f)
        _ = next(reader)
        valid_measuring_agencies = [row[0] for row in reader if row[1]=='Yes']
        logger.info(f'Valid Measuring Agencies: {valid_measuring_agencies}')
    return df[df["MeasuringAgency"].isin(valid_measuring_agencies)]


def filter_to_valid_point_ids(session: Session, df: pd.DataFrame) -> pd.DataFrame:
    valid_point_ids = get_valid_point_ids(session)
    return df[df["PointID"].isin(valid_point_ids)]


def convert_to_wgs84_vertical_datum(row, z):
    if row.VerticalDatum == "NAVD88":
        z = z + 2.0  # TODO: check this transformation
    elif row.VerticalDatum == "NGVD29":
        z = z + 3.0  # TODO: check this transformation
    return z


def convert_mt_to_utc(dt_record: datetime):
    t = dt_record.time()
    if t.hour == 0 and t.minute == 0:
        # no time was measured, so just set the timezone to UTC and keep
        # time at 00:00
        dt_record = dt_record.replace(tzinfo=timezone.utc)
    else:
        tz = pytz.timezone("America/Denver")
        dt_record = tz.localize(dt_record)
        if dt_record.dst() == timedelta(0):
            # MST
            utc_offset = 7
        else:
            # MDT
            utc_offset = 6
        dt_record = dt_record - timedelta(hours=utc_offset)
        dt_record = dt_record.replace(tzinfo=timezone.utc)
    return dt_record


def make_location(row: pd.Series) -> Location:
    point = Point(row.Easting, row.Northing)

    # Convert the point to a WGS84 coordinate system
    transformed_point = transform_srid(
        point, source_srid=SRID_UTM_ZONE_13N, target_srid=SRID_WGS84
    )

    # since this is such a time consuming operation, I do not want to run it during this step
    # cleanup_wells was added for this reason

    # state = get_state_from_point(transformed_point.x, transformed_point.y)
    # county = get_county_from_point(transformed_point.x, transformed_point.y)
    # quad_name = get_quad_name_from_point(transformed_point.x, transformed_point.y)

    z = row.Altitude
    if z:
        elevation_from_epqs = False
        z = z * 0.3048
    else:
        elevation_from_epqs = True
        logger.info(
            f"Location {row.PointID} has no Altitude. Setting from National Map EPQS for "
        )
        z = get_epqs_elevation_from_point(transformed_point.x, transformed_point.y)

    if elevation_from_epqs:
        elevation_method = "USGS National Elevation Dataset (NED)"
    elif not (pd.isna(row.AltitudeMethod)):
        elevation_method = lu_to_lexicon_map[f"LU_AltitudeMethod:{row.AltitudeMethod}"]
    else:
        elevation_method = None

    if not (pd.isna(row.CoordinateMethod)):
        coordinate_method = lu_to_lexicon_map[
            f"LU_CoordinateMethod:{row.CoordinateMethod}"
        ]
    else:
        coordinate_method = None

    """
    Developer's notes

    AMP folks said that the earlier date between DateCreated and SiteDate is when
    the site was inventoried, whereas the later is when the record was made in
    the database. This was because they were used interchangeably. 
    """
    if row.DateCreated and row.SiteDate:

        date_created = datetime.strptime(row.DateCreated, "%Y-%m-%d %H:%M:%S.%f")
        site_date = datetime.strptime(row.SiteDate, "%Y-%m-%d %H:%M:%S.%f")

        if date_created > site_date:
            created_at = date_created
        else:
            created_at = site_date
    elif row.DateCreated and not row.SiteDate:
        created_at = datetime.strptime(row.DateCreated, "%Y-%m-%d %H:%M:%S.%f")
    else:
        # TODO: should this be set to SiteDate if DateCreated is None and SiteDate is populated?
        created_at = None

    # convert created_at from MST/MDT to UTC
    if created_at is not None:
        created_at = convert_mt_to_utc(created_at)

    # TODO: AMP feedback is required for transfering coordinate accuracy values
    #       from NM_Aquifer to Ocotillo
    # if row.CoordinateAccuracy == "U" or pd.isna(row.CoordinateAccuracy):
    #     # map "Unknown" to None
    #     row.CoordinateAccuracy = None
    # elif row.CoordinateAccuracy == "5m":
    #     row.CoordinateAccuracy = 5.0
    # else:
    #     seconds = 0
    #     minutes = 0
    #     if row.CoordinateAccuracy == "1":
    #         seconds = 0.1
    #     elif row.CoordinateAccuracy == "5":
    #         seconds = 0.5
    #     elif row.CoordinateAccuracy == "F":
    #         seconds = 5
    #     elif row.CoordinateAccuracy == "H":
    #         seconds = 0.01
    #     elif row.CoordinateAccuracy == "M":
    #         minutes = 1
    #     elif row.CoordinateAccuracy == "R":
    #         seconds = 3
    #     elif row.CoordinateAccuracy == "S":
    #         seconds = 1
    #     else:
    #         seconds = 10
    #     coordinate_accuracy_decimal_deg = minutes/60 + seconds / 3600

    #     """
    #     Developer's notes

    #     To convert accuracy from decimal degrees to meters we do the following:

    #     1. Add the coordinate accuracy to both the latitude and longitude to
    #         find the "+" distance from the location
    #     2. Convert "+" accuracy coordinates from decimal degrees to UTM Zone 13
    #         N
    #     3. Find the distance in meters from the original Easting/Northing and
    #         define this as the "+" accuracy in meters
    #     4. Subtract the coordinate accuracy to both the latitude and longitude
    #         to find the "-" distance from the location
    #     5. Convert the "-" accuracy coordinates from decimal degrees to UTM Zone
    #         13 N
    #     6. Find the distance in meters from the original Easting/Northing and
    #         define this as the "-" accuracy in meters
    #     7. Set the coordinate accuracy in meters as the mean of the "+" and "-"
    #         distances from the location
    #     """
    #     original_longitude = transformed_point.x
    #     original_latitude = transformed_point.y

    #     plus_longitude = original_longitude + coordinate_accuracy_decimal_deg
    #     plus_latitude = original_latitude + coordinate_accuracy_decimal_deg
    #     plus_point_decimal_deg = Point(plus_longitude, plus_latitude)
    #     plus_point_utm_zone_13_n = transform_srid(
    #         plus_point_decimal_deg,
    #         SRID_WGS84,
    #         SRID_UTM_ZONE_13N)

    #     minus_longitude = original_longitude - coordinate_accuracy_decimal_deg
    #     minus_latitude = original_latitude - coordinate_accuracy_decimal_deg
    #     minus_point_decimal_deg = Point(minus_longitude, minus_latitude)

    location = Location(
        nma_pk_location=row.LocationId,
        # name=row.PointID,
        point=transformed_point.wkt,
        elevation=z,
        release_status="public" if row.PublicRelease else "private",
        elevation_accuracy=row.AltitudeAccuracy,
        elevation_method=elevation_method,
        created_at=created_at,
        # TODO: get AMP feedback on transfering these values. See above note
        # coordinate_accuracy=row.CoordinateAccuracy,
        coordinate_method=coordinate_method,
        nma_coordinate_notes=row.CoordinateNotes,
        nma_notes_location=row.LocationNotes,
        # these values will be populated in cleanup_wells
        # state=state,
        # county=county,
        # quad_name=quad_name,
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


def timeit_direct(func, *args, **kwargs):
    start = datetime.now()
    result = func(*args, **kwargs)
    end = datetime.now()
    logger.info(f"{func.__name__} took {(end - start).total_seconds()} seconds")
    return result


def timeit(func):
    def wrapper(*args, **kwargs):
        return timeit_direct(func, *args, **kwargs)

    return wrapper


if __name__ == "__main__":
    print(lu_to_lexicon_map)

# ============= EOF =============================================
