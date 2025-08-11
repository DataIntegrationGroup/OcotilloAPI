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

import time

import numpy as np
import pandas as pd
import pyproj
from shapely import Point
from shapely.ops import transform

from db import Location, LocationThingAssociation
from db.engine import session_ctx

# from db.observation.groundwaterlevel import GroundwaterLevelObservation

# from db.series.groundwaterlevel import GroundwaterLevelSeries
# from db.series.series import Series
from services.lexicon import add_lexicon_term
from services.thing_helper import add_thing


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


#
# def migrate_water_levels(session, limit=800):
#     wd = pd.read_csv("./migration/data/water_levels.csv")
#     p = pd.read_csv("./migration/data/welldata.csv")
#     # get first 100 rows
#     pointids = p["PointID"].unique()[:limit]
#
#     wd = wd[wd["PointID"].isin(pointids)]
#
#     gwd = wd.groupby(["PointID"])
#
#     sensor = Sensor()
#     sensor.name = '"manual gwl measurement. needs to be replaced with measurementmethod(?) e.g. steel tape, eprobe, etc."'
#     sensor.description = "Groundwater level manual measurement"
#     session.add(sensor)
#     session.commit()
#
#     for index, group in gwd:
#
#         # add a series
#         # add a groundwater level series
#         thing = session.query(Thing).filter_by(name=index[0]).first()
#         print("Processing PointID:", index, thing)
#         if not thing:
#             continue
#
#         print("found thing:", index, thing.id)
#         series = Series(name="Groundwater Level Series")
#         series.observed_property = "groundwater level"
#         series.unit = "ft"
#
#         series.sensor = sensor
#         series.thing = thing
#
#         groundwater_level_series = GroundwaterLevelSeries()
#         groundwater_level_series.series = series
#
#         session.add(series)
#         session.add(groundwater_level_series)
#
#         for row in group.itertuples():
#             obs = Observation()
#             obs.series = series
#             obs.observation_datetime = datetime.fromisoformat(row.DateMeasured)
#             # print("rw", row.DateMeasured, row.TimeMeasured)
#             gwl_obs = GroundwaterLevelObservation()
#             gwl_obs.observation = obs
#             gwl_obs.depth_to_water = row.DepthToWater
#             gwl_obs.measuring_point_height = row.MPHeight
#             session.add(obs)
#             session.add(gwl_obs)
#
#         session.commit()
#         # break
#
#         # print(group)
#         # print('--------------------------------------------')
#         # break
#         # for index, row in group:
#         # print(index, row)
#         # print(row.PointID, row.TimeMeasured)
#         # print(row.PointID, row.WaterLevel, row.WaterLevelDate)
#         # if pd.isna(row.WaterLevel) or pd.isna(row.WaterLevelDate):
#         #     continue
#         #
#         # obs = add_groundwater_level_observation(
#         #     session,
#         #     {
#         #         "point_id": row.PointID,
#         #         "water_level": row.WaterLevel,
#         #         "water_level_date": row.WaterLevelDate,
#         #     },
#         # )
#         # print(obs)
#
#         # print(index, row)
#
#         # obs = Observation()


ADDED = []


def transfer_springs(session, limit=10000):
    ldf = pd.read_csv("./data/location.csv")
    ldf = ldf[ldf["SiteType"] == "SP"]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    n = len(ldf)
    start_time = time.time()
    for i, row in enumerate(ldf.itertuples()):
        if i >= limit:
            print(f"Reached limit of {limit} rows. Stopping migration.")
            break

        if i and not i % 100:
            print(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        location = make_location(row)
        session.add(location)

        spring = add_thing(
            session,
            {
                "name": row.PointID,
                "thing_type": "spring",
                "release_status": "public" if row.PublicRelease else "private",
            },
        )
        assoc = LocationThingAssociation()

        assoc.location = location
        assoc.thing = spring
        session.add(assoc)


def transfer_wells(session, limit=1000):
    wdf = pd.read_csv("./data/welldata.csv")
    ldf = pd.read_csv("./data/location.csv")

    wdf = wdf.replace(pd.NA, None)
    wdf = wdf.replace({np.nan: None})

    wdf = wdf.join(ldf.set_index("PointID"), on="PointID")
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    n = len(wdf)
    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if i >= limit:
            print("Reached limit of", limit, "rows. Stopping migration.")
            break

        if i and not i % 100:
            print(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        location = make_location(row)
        session.add(location)

        well = add_thing(
            session,
            {
                "name": row.PointID,
                "hole_depth": row.HoleDepth,
                "well_depth": row.WellDepth,
                "well_casing_diameter": row.CasingDiameter,
                "well_casing_depth": row.CasingDepth,
                "well_casing_description": row.CasingDescription,
                "thing_type": "water well",
                "release_status": "public" if row.PublicRelease else "private",
            },
        )
        wt = row.Meaning
        if wt not in ADDED:
            add_lexicon_term(
                session, wt, "Current use of the well, aka well type", "current_use"
            )
            ADDED.append(wt)

        well.well_type = wt

        assoc = LocationThingAssociation()

        assoc.location = location
        assoc.thing = well
        session.add(assoc)
        # break


# def reset_db():
#     configure_mappers()
#
#     Base.metadata.drop_all(engine)
#     Base.metadata.create_all(engine)
#
#     init_hypertables()
#     init_lexicon()


if __name__ == "__main__":
    # reset_db()
    with session_ctx() as sess:
        transfer_wells(sess, limit=10000)
        transfer_springs(sess, limit=10000)
        # migrate_water_levels(sess)

# ============= EOF =============================================
