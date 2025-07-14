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
from datetime import datetime

import numpy as np
import pandas as pd
import pyproj
from shapely import Point
from shapely.ops import transform
from sqlalchemy.orm import configure_mappers

from api.observation import add_groundwater_level_observation
from core.app import init_hypertables, init_lexicon
from db import Location, LocationThingAssociation, Base, Thing, Sensor
from db.engine import session_ctx, engine
from db.observation.groundwaterlevel import GroundwaterLevelObservation
from db.observation.observation import Observation
from db.series.groundwaterlevel import GroundwaterLevelSeries
from db.series.series import Series
from services.lexicon import add_lexicon_term
from services.thing_helper import add_well


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
        # name=row_dict["PointID"],
        point=transformed_point.wkt,
        # visible=row_dict["PublicRelease"],
    )


def load_water_levels(session):
    wd = pd.read_csv('data/water_levels.csv')
    p = pd.read_csv('data/welldata.csv')
    # get first 100 rows
    pointids = p['PointID'].unique()[:100]


    wd = wd[wd['PointID'].isin(pointids)]

    gwd = wd.groupby(['PointID'])

    sensor = Sensor()
    sensor.name = '"manual gwl measurement. needs to be replaced with measurementmethod(?) e.g. steel tape, eprobe, etc."'
    sensor.description = "Groundwater level manual measurement"
    session.add(sensor)
    session.commit()

    for index, group in gwd:

        # add a series
        # add a groundwater level series
        thing = session.query(Thing).filter_by(name=index[0]).first()
        print('Processing PointID:', index, thing)
        if not thing:
            continue

        print('found thing:',index, thing.id)
        series = Series(name='Groundwater Level Series')
        series.observed_property = "groundwater level"
        series.unit = 'ft'

        series.sensor = sensor
        series.thing = thing

        groundwater_level_series = GroundwaterLevelSeries()
        groundwater_level_series.series = series

        session.add(series)
        session.add(groundwater_level_series)

        for row in group.itertuples():
            obs = Observation()
            obs.series = series
            obs.observation_timestamp = datetime.fromisoformat(row.DateMeasured)
            print('rw', row.DateMeasured, row.TimeMeasured)
            gwl_obs = GroundwaterLevelObservation()
            gwl_obs.observation = obs
            gwl_obs.depth_to_water = row.DepthToWater
            gwl_obs.measuring_point_height = row.MPHeight
            session.add(obs)
            session.add(gwl_obs)

        session.commit()
        # break

        # print(group)
        # print('--------------------------------------------')
        # break
        # for index, row in group:
            # print(index, row)
            # print(row.PointID, row.TimeMeasured)
            # print(row.PointID, row.WaterLevel, row.WaterLevelDate)
            # if pd.isna(row.WaterLevel) or pd.isna(row.WaterLevelDate):
            #     continue
            #
            # obs = add_groundwater_level_observation(
            #     session,
            #     {
            #         "point_id": row.PointID,
            #         "water_level": row.WaterLevel,
            #         "water_level_date": row.WaterLevelDate,
            #     },
            # )
            # print(obs)

        # print(index, row)

        # obs = Observation()





ADDED = []
def load_wells(session):
    wdf = pd.read_csv('data/welldata.csv')
    ldf = pd.read_csv('data/location.csv')


    wdf = wdf.replace(pd.NA, None)
    wdf = wdf.replace({np.nan: None})

    wdf = wdf.join(ldf.set_index('PointID'), on='PointID')
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    n = len(wdf)
    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if i and not i%100:
            print(f'Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}')
            session.commit()
            break

        location = make_location(row)
        session.add(location)

        well = add_well(
            session,
            {
                "name": row.PointID,
                "hole_depth": row.HoleDepth,
                "well_depth": row.WellDepth,
                "casing_diameter": row.CasingDiameter,
                "casing_depth": row.CasingDepth,
                "casing_description": row.CasingDescription,

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
        assoc.thing = well.thing
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


if __name__ == '__main__':
    # reset_db()
    with session_ctx() as sess:
        # load_wells(sess)
        load_water_levels(sess)

# ============= EOF =============================================
