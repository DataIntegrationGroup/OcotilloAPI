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
import numpy as np
import pandas as pd
import pyproj
from shapely import Point
from shapely.ops import transform
from sqlalchemy.exc import ProgrammingError

from db import Location
from db.engine import session_ctx
from db.thing.well import WellThing
from services.lexicon import add_lexicon_term

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


def extract_locations():
    """
    Extracts location data from the database.
    This function should connect to the database and retrieve location data.
    """
    df = pd.read_csv("data/location.csv")
    df = df[df["SiteType"] == "GW"]
    df = df[df["Easting"].notna() & df["Northing"].notna()]
    return df


def extract_wells():
    """
    Extracts well data from the database.
    This function should connect to the database and retrieve well data.
    """
    df = pd.read_csv("data/welldata.csv")
    return df


def transform_locations(df):
    return df


def transform_wells(df):
    # cover nans to nulls
    df = df.replace(pd.NA, None)
    df = df.replace({np.nan: None})

    return df


def load_locations(sess, df):
    for row in df.itertuples():
        # Convert the row to a dictionary
        row_dict = row._asdict()

        e, n = row_dict["Easting"], row_dict["Northing"]

        point = Point(e, n)
        transformed_point = transform_srid(
            point, source_srid=26913, target_srid=4326  # WGS84 SRID
        )

        sl = Location(
            name=row_dict["PointID"],
            point=transformed_point.wkt,
            visible=row_dict["PublicRelease"],
        )

        sess.add(sl)
        try:
            sess.commit()  # Commit the changes to the database
        except ProgrammingError:
            print(f"skipping row due to ProgrammingError. {row_dict['PointID']}")
            sess.rollback()
        # Remove the index from the dictionary


def load_wells(sess, df):

    # print(df.head())
    n = len(df)

    for i, row in enumerate(df.itertuples()):
        if not i % 100:
            print(f"Processing row {i} of {n}")

        row_dict = row._asdict()

        location = (
            sess.query(Location).filter_by(name=row_dict["PointID"]).one_or_none()
        )

        if location:
            well = WellThing()
            well.location = location
            well.well_depth = row_dict["WellDepth"]
            well.hole_depth = row_dict["HoleDepth"]
            well.ose_pod_id = row_dict["OSEWellID"]
            well.casing_depth = row_dict["CasingDepth"]
            well.casing_diameter = row_dict["CasingDiameter"]
            well.casing_description = row_dict["CasingDescription"]

            wt = row_dict["Meaning"]

            add_lexicon_term(
                sess, wt, "Current use of the well, aka well type", "current_use"
            )

            well.well_type = wt

            # print(row_dict)
            sess.add(well)
            sess.commit()
            # break


def location_etl(sess):
    """
    Extract, Transform, Load (ETL) process for location data.
    """
    df = extract_locations()
    df = transform_locations(df)
    load_locations(sess, df)


def well_etl(sess):
    """
    Extract, Transform, Load (ETL) process for well data.
    """
    df = extract_wells()
    df = transform_wells(df)
    load_wells(sess, df)


if __name__ == "__main__":
    with session_ctx() as session:
        # location_etl(session)
        well_etl(session)
        session.close()
# ============= EOF =============================================
