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

from pandas import isna
from pydantic import ValidationError
from sqlalchemy.orm import Session

from db import LocationThingAssociation
from services.thing_helper import add_thing
from transfers.logger import logger
from transfers.util import (
    make_location,
    make_location_data_provenance,
    read_csv,
    replace_nans,
)


def transfer_thing(session: Session, site_type: str, make_payload, limit=None) -> None:

    ldf = read_csv("Location")
    ldf = ldf[ldf["SiteType"] == site_type]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    ldf = replace_nans(ldf)
    n = len(ldf)
    start_time = time.time()

    logger.info("Starting transfer: Things (%s) [%s rows]", site_type, n)
    cached_elevations = {}

    for i, row in enumerate(ldf.itertuples()):
        pointid = row.PointID
        if ldf[ldf["PointID"] == pointid].shape[0] > 1:
            logger.critical(f"PointID {pointid} has duplicate records. Skipping.")
            continue

        if limit is not None and limit > 0 and i >= limit:
            logger.warning(f"Reached limit of {limit} rows. Stopping migration.")
            break

        if i and not i % 25:
            logger.info(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        try:
            location, elevation_method, location_notes = make_location(
                row, cached_elevations
            )
            session.add(location)
            session.flush()
            for note_type, note_content in location_notes.items():
                if not isna(note_content):
                    location_note = location.add_note(note_content, note_type)
                    session.add(location_note)

            data_provenances = make_location_data_provenance(
                row, location, elevation_method
            )
            for dp in data_provenances:
                session.add(dp)

            payload = make_payload(row)
            thing_type = payload.pop("thing_type")
            payload["nma_pk_location"] = row.LocationId
            thing = add_thing(session, payload, thing_type=thing_type)
            assoc = LocationThingAssociation()
            assoc.location = location
            assoc.thing = thing
            session.add(assoc)
        except ValidationError as e:
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
        except Exception as e:
            logger.critical(f"Error creating location for {row.PointID}: {e}")
            continue

    session.commit()
    logger.info("Completed transfer: Things (%s)", site_type)


def _release_status(row) -> str:
    return "public" if row.PublicRelease else "private"


def transfer_springs(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "spring",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "SP", make_payload, limit)


def transfer_perennial_streams(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "perennial stream",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "PS", make_payload, limit)


def transfer_ephemeral_streams(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "ephemeral stream",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "ES", make_payload, limit)


def transfer_met_stations(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "meteorological station",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "M", make_payload, limit)


def transfer_rock_sample_locations(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "rock sample location",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "R", make_payload, limit)


def transfer_diversion_of_surface_water(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "diversion of surface water, etc.",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "D", make_payload, limit)


def transfer_lake_pond_reservoir(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "lake, pond or reservoir",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "L", make_payload, limit)


def transfer_soil_gas_sample_locations(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "soil gas sample location",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "S", make_payload, limit)


def transfer_other_site_types(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "other",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "OT", make_payload, limit)


def transfer_outfall_wastewater_return_flow(session, limit=None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "outfall of wastewater or return flow",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "O", make_payload, limit)


# ============= EOF =============================================
