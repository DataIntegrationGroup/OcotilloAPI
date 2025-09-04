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
from pydantic import ValidationError
from sqlalchemy import select

from db import LocationThingAssociation, Thing, WellScreen, Location
from services.crud_helper import model_adder
from schemas.thing import CreateWellScreen
from services.lexicon_helper import add_lexicon_term
from services.thing_helper import add_thing
from transfers.util import (
    make_location,
    filter_to_valid_point_ids,
    read_csv,
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)

ADDED = []


def transfer_wells(session, limit=None):
    wdf = read_csv("welldata.csv")
    ldf = read_csv("location.csv")

    wdf = wdf.join(ldf.set_index("PointID"), on="PointID")
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    n = len(wdf)
    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if limit and i >= limit:
            print("Reached limit of", limit, "rows. Stopping migration.")
            break

        if i and not i % 25:
            print(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        try:
            location = make_location(row)
        except Exception as e:
            print(f"Error making location for row {i}: {e}")
            break

        # print(location_row)
        session.add(location)

        well = add_thing(
            session,
            {
                # "nma_pk_welldata": row.WellID,
                "name": row.PointID,
                "hole_depth": row.HoleDepth,
                "well_depth": row.WellDepth,
                # "driller_name": row.DrillerName,
                # "construction_method": row.ConstructionMethod,
                # "casing_diameter": row.CasingDiameter,
                # "casing_depth": row.CasingDepth,
                # "casing_description": row.CasingDescription,
                "release_status": "public" if row.PublicRelease else "private",
                # "data_reliability": row.DataReliability,
            },
            thing_type="water well",
        )
        wt = row.Meaning
        if wt not in ADDED:
            add_lexicon_term(
                session,
                wt,
                "Current use of the well, aka well purpose",
                [{"name": "current_use", "desciption": "Current use of the well"}],
            )
            ADDED.append(wt)

        well.well_type = wt

        assoc = LocationThingAssociation()

        assoc.location = location
        assoc.thing = well
        session.add(assoc)


def transfer_wellscreens(session, limit=None):
    wdf = read_csv("wellscreens.csv")
    wdf = wdf.replace(pd.NA, None)
    wdf = wdf.replace({np.nan: None})

    wdf = filter_to_valid_point_ids(session, wdf)

    n = len(wdf)

    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if limit and i >= limit:
            print("Reached limit of", limit, "rows. Stopping migration.")
            break

        # this is for testing only. not sure in practice we have to commit every 100 rows
        # should we commit every row? or every 1000? or every 10?
        if i and not i % 100:
            print(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

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
            setattr(model, "nma_pk_wellscreens", row.GlobalID)
            model_adder(session, WellScreen, model)
        except ValidationError as e:
            print(f"Validation error for row {i} with PointID {row.PointID}: {e}")
            continue


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
