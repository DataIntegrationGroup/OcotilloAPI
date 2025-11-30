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
import io
import math
import os
import re
import time
from datetime import datetime, timezone, timedelta, UTC
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
from shapely import Point
from sqlalchemy import select

from constants import SRID_WGS84, SRID_UTM_ZONE_13N
from db import Thing, Location, DataProvenance, Parameter
from db.engine import session_ctx
from services.gcs_helper import get_storage_bucket

# from services.lexicon_mapper import lexicon_mapper
from services.util import (
    transform_srid,
    get_epqs_elevation_from_point,
    convert_ft_to_m,
    convert_ngvd29_to_navd88,
)
from transfers.logger import logger

NMA_COORDINATE_ACCURACY = {
    "5m": (5, "m"),
    "1": (0.1, "second"),
    "5": (0.5, "second"),
    "F": (5, "second"),
    "H": (0.01, "second"),
    "M": (1, "minute"),
    "R": (3, "second"),
    "S": (1, "second"),
    "T": (10, "second"),
}


class MeasuringPointEstimator:
    def __init__(self):
        df = read_csv("WaterLevels")
        df["DateMeasured"] = pd.to_datetime(df["DateMeasured"], errors="coerce")
        self._df = df.dropna(subset=["DateMeasured"])

    def estimate_measuring_point_height(
        self, row
    ) -> tuple[float, str, datetime | None]:
        mph = row.MPHeight
        mph_desc = row.MeasuringPoint

        df = self._df[self._df["PointID"] == row.PointID]
        df = df.sort_values("DateMeasured")
        if mph is None:
            logger.info(
                f"No MPHeight found for PointID: {row.PointID}. Estimating from measurements."
            )
            mphs = []
            start_dates = []
            mph_descs = []

            if len(df) == 0:
                logger.warning(f"No measurements found for PointID: {row.PointID}.")
            else:
                # try to estimate mpheight from measurements
                for m in df.itertuples():
                    mphi = m.DepthToWater - m.DepthToWaterBGS
                    start_date = m.DateMeasured
                    if mphi not in mphs:
                        mphs.append(mphi)
                        mph_descs.append(
                            "Auto calculated from measurements at depth to water and depth to water below ground surface"
                        )
                        start_dates.append(start_date)
                logger.info(
                    f"Estimated MPHeight: {mphs}, {start_dates} for PointID: {row.PointID}."
                )
        else:
            mphs = [mph]
            mph_descs = [mph_desc]
            if len(df) > 0:
                start_dates = [df["DateMeasured"].min()]
            else:
                start_dates = [datetime.now(tz=UTC)]

        if len(mphs) == 1:
            end_dates = [None]
        else:
            end_dates = [start_dates[i + 1] for i in range(len(start_dates) - 1)]
            end_dates.append(None)

        return zip(mphs, mph_descs, start_dates, end_dates)


class SensorParameterEstimator:
    def __init__(self, sensor_type: str):
        if sensor_type == "Pressure Transducer":
            self._df = read_csv("WaterLevelsContinuous_Pressure")
        else:
            self._df = read_csv("WaterLevelsContinuous_Acoustic")

        # convert "DateMeasured" to date"
        self._df["DateMeasured"] = pd.to_datetime(self._df["DateMeasured"]).dt.date

    def estimate_installation_date(
        self, record: pd.Series
    ) -> tuple[datetime | None, str | None]:
        # get the first measurement for this pointid
        point_id = record.PointID
        cdf = self._get_values(point_id)
        if len(cdf) == 0:
            logger.warning(
                f"Unable to estimate installation date, no measurements found for PointID: {point_id}."
            )
            return None
        return cdf["DateMeasured"].min()

    def _get_values(self, point_id: str):
        cdf = self._df[self._df["PointID"] == point_id]
        return cdf.sort_values("DateMeasured")

    def estimate_recording_interval(
        self,
        record: pd.Series,
        installation_date: datetime = None,
        removal_date: datetime = None,
    ) -> tuple[int | None, str | None, str | None]:
        point_id = record.PointID
        cdf = self._get_values(point_id)
        if len(cdf) == 0:
            return None, None, f"No measurements found for PointID: {point_id}"

        if installation_date is not None:
            cdf = cdf[cdf["DateMeasured"] >= installation_date]
        if removal_date is not None:
            cdf = cdf[cdf["DateMeasured"] <= removal_date]

        # calculate the average interval in seconds
        try:
            date_series = pd.to_datetime(cdf["DateMeasured"])
            intervals = date_series.diff().dropna().dt.total_seconds()
            if len(intervals) == 0:
                logger.warning(
                    f"No intervals found for {point_id} for time range "
                    f"{installation_date}-{removal_date}. using entire series "
                )
                # take average of entire series
                df = self._df[self._df["PointID"] == point_id]
                df = df.sort_values("DateMeasured")
                date_series = pd.to_datetime(df["DateMeasured"])
                intervals = date_series.diff().dropna().dt.total_seconds()
                if len(intervals) == 0:
                    return (
                        None,
                        None,
                        f"No measurements found for {point_id} for entire series",
                    )
                else:
                    avg_interval = intervals.mean()
            else:
                avg_interval = intervals.mean()
        except IndexError:
            return (
                None,
                None,
                (
                    f"Not enough measurements to calculate interval for PointID: {point_id},"
                    f"{installation_date} to {removal_date}."
                ),
            )

        # convert to hours
        avg_interval /= 3600

        unit = "hour"
        if avg_interval < 0.95:  # if less then 57 minutes convert to minutes
            avg_interval *= 60
            unit = "minute"
            if avg_interval < 0.95:  # if less then 57 seconds convert to seconds
                avg_interval *= 60
                unit = "second"

        return math.ceil(avg_interval), unit, None


def replace_nans(df: pd.DataFrame, default=None) -> pd.DataFrame:
    df = df.replace(pd.NA, default)
    return df.replace({np.nan: default})


def read_csv(name: str, dtype: dict | None = None, *args, **kw) -> pd.DataFrame:
    p = get_transfers_data_path(Path("nma_csv_cache") / f"{name}.csv")
    if os.path.exists(p):
        logger.info(f"Using cached csv: {p}")
        starttime = time.time()
        df = pd.read_csv(p, dtype=dtype, *args, **kw)
        logger.info(f"Read csv in {time.time()-starttime:0.2f}")
        return df
    else:
        logger.info(f"Downloading csv: {name}")

    bucket = get_storage_bucket()
    blob = bucket.blob(f"nma_csv/{name}.csv")
    data = blob.download_as_bytes()
    with open(p, "wb") as f:
        f.write(data)

    return pd.read_csv(io.BytesIO(data), dtype=dtype)


def get_valid_point_ids(thing_type="water well"):
    with session_ctx() as session:
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


def get_transfers_data_path(name):
    def data_path(r):
        return Path(r) / "transfers" / "data"

    root = data_path("/workspace")
    if not os.path.exists(root):
        root = data_path("..")
        if not os.path.exists(root):
            root = data_path(".")

    return root / name


def filter_non_transferred_wells(df: pd.DataFrame) -> pd.DataFrame:
    with session_ctx() as sess:
        sql = select(Thing.name).where(Thing.thing_type == "water well")
        existing_ids = sess.execute(sql).scalars().all()
    return df[~(df["PointID"].isin(existing_ids))]


def filter_by_welldata_datasource_and_project(df: pd.DataFrame) -> pd.DataFrame:
    path = get_transfers_data_path("valid_welldata_datasources.csv")
    with open(path, "r") as f:
        reader = csv.reader(f)
        _ = next(reader)
        valid_datasources = [row[0] for row in reader if row[1] == "Yes"]

        # f.seek(0)
        # invalid_datasources = [row[0] for row in reader if row[1] == "NO"]
        # logger.info("Invalid WellData Datasources:")
        # for vd in invalid_datasources:
        #     logger.info(f"  {vd}")

    counts = df.groupby("DataSource").size().reset_index(name="WellCount")
    counts = counts.sort_values("WellCount", ascending=False)
    for count in counts.itertuples():
        logger.info(f"{count.WellCount}: {count.DataSource[:50]} ")

    pldf = read_csv("ProjectLocations")
    collabnet = pldf[pldf["ProjectName"] == "Water Level Network"]
    return df[
        df["DataSource"].isin(valid_datasources)
        | df["PointID"].isin(collabnet["PointID"])
    ]


def filter_by_valid_measuring_agency(df: pd.DataFrame) -> pd.DataFrame:
    path = get_transfers_data_path("valid_measuring_agency.csv")

    with open(path, "r") as f:
        reader = csv.reader(f)
        _ = next(reader)
        valid_measuring_agencies = [row[0] for row in reader if row[1] == "Yes"]
        logger.info("Valid Measuring Agencies:")
        for vma in valid_measuring_agencies:
            logger.info(f"  {vma}")
    return df[df["MeasuringAgency"].isin(valid_measuring_agencies)]


def filter_to_valid_point_ids(df: pd.DataFrame) -> pd.DataFrame:
    valid_point_ids = get_valid_point_ids()
    return df[df["PointID"].isin(valid_point_ids)]


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


def chunk_by_size(df, chunk_size):
    for i in range(0, len(df), chunk_size):
        yield df.iloc[i : i + chunk_size]


def get_groundwater_parameter_id():
    with session_ctx() as session:
        groundwater_parameter_id = (
            session.query(Parameter)
            .filter(Parameter.parameter_name == "groundwater level")
            .one()
            .id
        )
    return groundwater_parameter_id


def make_location(row: pd.Series, elevations: dict) -> tuple:
    """
    Returns a tuple of location data and the elevation method
    """
    point = Point(row.Easting, row.Northing)

    # Convert the point to a WGS84 coordinate system
    transformed_point = transform_srid(
        point, source_srid=SRID_UTM_ZONE_13N, target_srid=SRID_WGS84
    )

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
    elif not row.DateCreated and row.SiteDate:
        created_at = datetime.strptime(row.SiteDate, "%Y-%m-%d %H:%M:%S.%f")
    else:
        created_at = None

    # convert created_at from MST/MDT to UTC
    if created_at is not None:
        created_at = convert_mt_to_utc(created_at)

    z = row.Altitude
    if z:
        elevation_from_epqs = False
        z = convert_ft_to_m(z)

        if row.AltDatum == "NGVD29":
            key = f"{row.PointID}, {transformed_point.x, transformed_point.y}"
            if key in elevations:
                z = elevations[key]
            else:
                z = convert_ngvd29_to_navd88(
                    z, transformed_point.x, transformed_point.y
                )
            elevations[key] = z
    else:
        elevation_from_epqs = True
        logger.info(
            f"Location {row.PointID} has no Altitude. Setting from National Map EPQS for "
        )
        z = get_epqs_elevation_from_point(transformed_point.x, transformed_point.y)

    if elevation_from_epqs:
        elevation_method = "USGS National Elevation Dataset (NED)"
    elif pd.isna(row.AltitudeMethod):
        elevation_method = None
    else:
        elevation_method = lexicon_mapper.map_value(
            f"LU_AltitudeMethod:{row.AltitudeMethod.strip()}"
        )

    location = Location(
        nma_pk_location=row.LocationId,
        point=transformed_point.wkt,
        elevation=z,
        release_status="public" if row.PublicRelease else "private",
        created_at=created_at,
        nma_coordinate_notes=row.CoordinateNotes,
        nma_notes_location=row.LocationNotes,
    )

    return location, elevation_method


def make_location_data_provenance(
    row: pd.Series, location: Location, elevation_method: str | None
) -> list[DataProvenance]:
    provenance_records = []

    if row.AltitudeAccuracy or row.CoordinateAccuracy:
        provenance = DataProvenance(
            target_id=location.id,
            target_table="location",
            field_name="elevation",
            origin_source=None,
            collection_method=elevation_method,
            accuracy_value=(
                None
                if pd.isna(row.AltitudeAccuracy)
                else convert_ft_to_m(row.AltitudeAccuracy)
            ),
            accuracy_unit="m",
        )
        provenance_records.append(provenance)

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

    if row.CoordinateMethod or row.CoordinateAccuracy:
        coordinate_method = (
            lexicon_mapper.map_value(f"LU_CoordinateMethod:{row.CoordinateMethod}")
            if not pd.isna(row.CoordinateMethod)
            else None
        )

        accuracy_value, accuracy_unit = NMA_COORDINATE_ACCURACY.get(
            row.CoordinateAccuracy, (None, None)
        )

        provenance = DataProvenance(
            target_id=location.id,
            target_table="location",
            field_name="point",
            origin_source=None,
            collection_method=coordinate_method,
            accuracy_value=accuracy_value,
            accuracy_unit=accuracy_unit,
        )
        provenance_records.append(provenance)

    return provenance_records


def timeit_direct(func, *args, **kwargs):
    start = datetime.now()
    result = func(*args, **kwargs)
    end = datetime.now()
    logger.info(f"TIMING: {func.__name__} took {(end - start).total_seconds()} seconds")
    return result


def timeit(func):
    def wrapper(*args, **kwargs):
        return timeit_direct(func, *args, **kwargs)

    return wrapper


class LexiconMapper:
    def __init__(self):
        self._mappers = None

    def map_value(self, value):
        value = value.strip()
        return self._make_lu_to_lexicon_mapper().get(value, value)

    def _make_lu_to_lexicon_mapper(self):
        if self._mappers:
            return self._mappers

        # Lookup tables where CODE maps to MEANING
        lu_tables = [
            "LU_AltitudeMethod",
            "LU_CollectionMethod",
            "LU_ConstructionMethod",
            "LU_CoordinateAccuracy",
            "LU_CoordinateMethod",
            "LU_CurrentUse",
            "LU_DataQuality",
            "LU_DataSource",
            "LU_Depth_CompletionSource",
            "LU_Discharge_ChemistrySource",
            "LU_LevelStatus",
            "LU_MajorAnalyte",
            "LU_MeasurementMethod",
            "LU_MinorTraceAnalyte",
            "LU_MonitoringStatus",
            "LU_SampleType",
            "LU_SiteType",
            "LU_Status",
        ]

        # Lookup tables intentionally skipped (kept for documentation only)
        # Each entry explains why the table is excluded
        _lu_tables_skipped = {
            "LU_AltitudeDatum": "code is the value, so no need for mapping",
            "LU_CoordinateDatum": "code is the value, so no need for mapping",
            "LU_FieldNoteTypes": "not being used in the transfers since there are no records",
            "LU_Formations": "needs to be cleaned before it can be used",
            "LU_Lithology": "needs to be cleaned before it can be used",
            "LU_MeasuringAgency": "the abbreviation is what is used in the new schema",
        }
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
        self._mappers = mappers
        return mappers


lexicon_mapper = LexiconMapper()


# ============= EOF =============================================
