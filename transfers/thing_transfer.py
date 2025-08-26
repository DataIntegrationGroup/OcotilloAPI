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

from sqlalchemy.orm import Session
import pandas as pd

from db import LocationThingAssociation
from services.thing_helper import add_thing
from transfers.util import make_location


def transfer_thing(session: Session, site_type: str, make_payload, limit=None) -> None:
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


# ============= EOF =============================================
