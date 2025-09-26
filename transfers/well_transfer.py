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
from pydantic import ValidationError
from sqlalchemy import select

from db import LocationThingAssociation, Thing, WellScreen, Location
from schemas.thing import CreateWellScreen, CreateWell
from services.thing_helper import add_thing
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
from transfers.util import (
    make_location,
    filter_to_valid_point_ids,
    read_csv,
    logger,
    replace_nans,
    filter_by_welldata_datasource,
)

ADDED = []


def transfer_wells(session, limit=0):
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    ldf = read_csv("Location")
    ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1)
    wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    wdf = replace_nans(wdf)

    # todo: filter Locations by DataSource
    wdf = filter_by_welldata_datasource(wdf)

    n = len(wdf)

    step = 25
    start_time = time.time()
    for i, row in enumerate(wdf.itertuples()):
        pointid = row.PointID
        if wdf[wdf["PointID"] == pointid].shape[0] > 1:
            logger.critical(f"transfer_wells. PointID {pointid} has duplicate records. Skipping.")
            continue

        if limit and i >= limit:
            logger.info(f"Reached limit of {limit} rows. Stopping migration.")
            break

        if i and not i % step:
            logger.info(
                f"Processing row {i} of {n},  avg rows per second: {step / (time.time() - start_time):.2f}"
            )
            start_time = time.time()

        try:
            location = make_location(row)
        except Exception as e:
            logger.critical(f"Error making location for {row.PointID}: {e}")
            continue

        session.add(location)

        # TODO: add guards for null values
        # TODO: use schema to validate

        data = CreateWell(
            # "nma_pk_welldata": row.WellID,
            name=row.PointID,
            hole_depth=row.HoleDepth,
            well_depth=row.WellDepth,
            well_construction_notes=row.ConstructionNotes,
            # "driller_name": row.DrillerName,
            # "construction_method": row.ConstructionMethod,
            # "casing_diameter": row.CasingDiameter,
            # "casing_depth": row.CasingDepth,
            # "casing_description": row.CasingDescription,
            release_status="public" if row.PublicRelease else "private",
            # "data_reliability": row.DataReliability,
        )
        try:
            well = add_thing(
                session,
                data,
                thing_type="water well",
            )
        except Exception as e:
            session.rollback()
            logger.critical(f"Error creating well for {row.PointID}: {e}")
            continue
        # TODO: use current use LUT to get well type

        # wt = row.Meaning
        # if wt not in ADDED:
        #     add_lexicon_term(
        #         session,
        #         wt,
        #         "Current use of the well, aka well purpose",
        #         [{"name": "current_use", "desciption": "Current use of the well"}],
        #     )
        #     ADDED.append(wt)
        #
        # well.well_type = wt

        assoc = LocationThingAssociation()

        assoc.location = location
        assoc.thing = well
        session.add(assoc)

        try:
            session.commit()
        except Exception as e:
            logger.critical(f"Error committing well {row.PointID}: {e}")
            session.rollback()
            continue


def transfer_wellscreens(session, limit=None):
    wdf = read_csv("WellScreens")
    wdf = replace_nans(wdf)

    wdf = filter_to_valid_point_ids(session, wdf)

    n = len(wdf)

    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if limit and i >= limit:
            logger.warning("Reached limit of", limit, "rows. Stopping migration.")
            break

        # this is for testing only. not sure in practice we have to commit every 100 rows
        # should we commit every row? or every 1000? or every 10?
        if i and not i % 100:
            logger.info(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        sql = select(Thing).where(Thing.name == row.PointID)
        thing = session.execute(sql).scalar_one_or_none()
        if not thing:
            logger.warning(
                f"Thing with PointID {row.PointID} not found. Skipping well screen."
            )
            continue

        well_screen_data = {
            "thing_id": thing.id,
            "screen_depth_top": row.ScreenTop,
            "screen_depth_bottom": row.ScreenBottom,
            # "screen_type": row.ScreenType,
            "screen_description": row.ScreenDescription,
            "release_status": "draft",
            "nma_pk_wellscreens": row.GlobalID,
        }
        try:
            # TODO: add validation logic here to ensure no overlapping screens for the same well
            CreateWellScreen.model_validate(well_screen_data)
            well_screen = WellScreen(**well_screen_data)
            session.add(well_screen)
        except ValidationError as e:
            logger.warning(
                f"Validation error for row {i} with PointID {row.PointID}: {e}"
            )
            continue

    session.commit()


def cleanup_wells(session):
    locations = session.query(Location).all()
    for location in locations:

        y, x = location.latlon
        if not location.state:
            location.state = get_state_from_point(x, y)

        if not location.county:
            location.county = get_county_from_point(x, y)

        if not location.quad_name:
            location.quad_name = get_quad_name_from_point(x, y)

    session.commit()


# ============= EOF =============================================
