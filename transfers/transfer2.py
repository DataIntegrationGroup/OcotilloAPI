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
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
import pyproj
from pydantic import ValidationError
from shapely import Point
from shapely.ops import transform
from sqlalchemy import select

from core.app import init_lexicon
from db import (
    Location,
    LocationThingAssociation,
    adder,
    WellScreen,
    Thing,
    Observation,
    Sample,
    Contact,
    Email,
    Phone,
    ThingContactAssociation,
    Base,
    Sensor,
    Address,
)
from db.engine import session_ctx
from schemas.thing import CreateWellScreen

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


def transfer_water_levels(session):
    wd = pd.read_csv("./data/water_levels.csv")
    gwd = wd.groupby(["PointID"])

    for index, group in gwd:
        for row in group.itertuples():
            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                print(f"Skipping row {row.Index} due to missing data.")
                continue

            dt = datetime.fromisoformat(row.DateMeasured)
            thing = session.query(Thing).where(Thing.name == row.PointID).first()
            if thing is None:
                print(
                    f"Thing with PointID {row.PointID} not found. Skipping water level."
                )
                continue

            sample = Sample()
            sample.sampler_name = "unknown"
            sample.sample_type = "groundwater level"

            sample.field_sample_id = str(uuid.uuid4())
            sample.sample_date = dt
            sample.thing = thing
            session.add(sample)

            obs = Observation()
            obs.sensor_id = 1
            obs.sample = sample
            obs.observation_datetime = dt
            obs.depth_to_water = row.DepthToWater
            obs.observed_property = "groundwater level"
            obs.unit = "ft"

            session.add(obs)
            session.commit()


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


def transfer_thing(session, site_type, make_payload, limit=None):
    ldf = pd.read_csv("./data/location.csv")
    ldf = ldf[ldf["SiteType"] == site_type]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    n = len(ldf)
    start_time = time.time()
    for i, row in enumerate(ldf.itertuples()):
        if limit and i >= limit:
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
            make_payload(row),
        )
        assoc = LocationThingAssociation()

        assoc.location = location
        assoc.thing = spring
        session.add(assoc)


def transfer_springs(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "spring",
            "release_status": "public" if row.PublicRelease else "private",
        }

    transfer_thing(session, "SP", make_payload, limit)


def transfer_perennial_stream(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "perennial stream",
            "release_status": "public" if row.PublicRelease else "private",
        }

    transfer_thing(session, "PS", make_payload, limit)


def transfer_ephemeral_stream(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "ephemeral stream",
            "release_status": "public" if row.PublicRelease else "private",
        }

    transfer_thing(session, "ES", make_payload, limit)


def transfer_met(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "meteorological station",
            "release_status": "public" if row.PublicRelease else "private",
        }

    transfer_thing(session, "M", make_payload, limit)


def transfer_owners(session):
    odf = pd.read_csv("./data/ownersdata.csv")
    odf = odf.replace(pd.NA, None)
    odf = odf.replace({np.nan: None})

    for i, row in odf.iterrows():
        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        if thing is None:
            print(f"Thing with PointID {row.PointID} not foaund. Skipping owner.")
            continue

        contact1 = Contact(name=f"{row.FirstName} {row.LastName}", role="Primary")
        assoc = ThingContactAssociation()
        assoc.thing = thing
        assoc.contact = contact1
        session.add(assoc)
        session.add(contact1)

        if row.Email:
            contact1.emails.append(Email(email=row.Email, email_type="Primary"))
        if row.Phone:
            contact1.phones.append(Phone(phone_number=row.Phone, phone_type="Primary"))
        if row.CellPhone:
            contact1.phones.append(
                Phone(phone_number=row.CellPhone, phone_type="Mobile")
            )

        if row.MailingAddress:
            contact1.addresses.append(
                Address(
                    address_line_1=row.MailingAddress,
                    city=row.MailCity,
                    state=row.MailState,
                    postal_code=row.MailZipCode,
                    address_type="Mailing",
                )
            )

            contact1.addresses.append(
                Address(
                    address_line_1=row.PhysicalAddress,
                    city=row.PhysicalCity,
                    state=row.PhysicalState,
                    postal_code=row.PhysicalZipCode,
                    address_type="Physical",
                )
            )

        contact2 = Contact(
            name=f"{row.SecondFirstName} {row.SecondLastName}", role="Secondary"
        )
        if row.SecondCtctEmail:
            contact2.emails.append(
                Email(email=row.SecondCtctEmail, email_type="Primary")
            )
        if row.SecondCtctPhone:
            contact2.phones.append(
                Phone(phone_number=row.SecondCtctPhone, phone_type="Primary")
            )

        assoc = ThingContactAssociation()
        assoc.thing = thing
        assoc.contact = contact2
        session.add(assoc)
        session.add(contact2)

        session.commit()


def transfer_wells(session, limit=None):
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
        if limit and i >= limit:
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


def transfer_wellscreens(session, limit=None):
    wdf = pd.read_csv("./data/wellscreens.csv")
    wdf = wdf.replace(pd.NA, None)
    wdf = wdf.replace({np.nan: None})

    n = len(wdf)
    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if limit and i >= limit:
            print("Reached limit of", limit, "rows. Stopping migration.")
            break

        if i and not i % 100:
            print(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()
        # thing_id: int
        # screen_depth_bottom: float
        # screen_depth_top: float
        # screen_type: str | None = None
        # print(row)

        sql = select(Thing).where(Thing.name == row.PointID)
        thing = session.execute(sql).scalar_one_or_none()
        if not thing:
            print(f"Thing with PointID {row.PointID} not found. Skipping well screen.")
            continue

        well_screen_data = {
            "thing_id": thing.id,
            "screen_depth_top": row.ScreenTop,
            "screen_depth_bottom": row.ScreenBottom,
            # "screen_type": row.ScreenType,
            "screen_description": row.ScreenDescription,
            "release_status": "draft",
        }
        try:
            model = CreateWellScreen.model_validate(well_screen_data)
            adder(session, WellScreen, model)
        except ValidationError as e:
            print(f"Validation error for row {i} with PointID {row.PointID}: {e}")
            continue
        # session.add(screen)


def init_sensor(session):
    sensor = Sensor()
    sensor.name = '"manual gwl measurement. needs to be replaced with measurementmethod(?) e.g. steel tape, eprobe, etc."'
    sensor.description = "Groundwater level manual measurement"
    sensor.unit = "ft"
    sensor.datetime_installed = datetime.now()
    session.add(sensor)
    session.commit()


if __name__ == "__main__":

    with session_ctx() as sess:
        Base.metadata.drop_all(sess.bind)
        Base.metadata.create_all(sess.bind)

        init_lexicon("../core/lexicon.json")

        init_sensor(sess)
        transfer_wells(sess, 1000)
        transfer_springs(sess, limit=1000)
        transfer_perennial_stream(sess)
        transfer_ephemeral_stream(sess)
        transfer_met(sess)

        transfer_owners(sess)
        transfer_wellscreens(sess)
        transfer_water_levels(sess)

# ============= EOF =============================================
