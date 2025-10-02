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
import os

from dotenv import load_dotenv

from transfers.asset_transfer import transfer_assets
from transfers.thing_transfer import (
    transfer_springs,
    transfer_perennial_stream,
    transfer_ephemeral_stream,
    transfer_met,
)

load_dotenv()

from sqlalchemy.orm import Session
from core.initializers import init_lexicon
from db import Base
from db.engine import session_ctx

from transfers.group_transfer import transfer_groups
from transfers.link_ids_transfer import transfer_link_ids, transfer_link_ids_welldata
from transfers.contact_transfer import transfer_contacts
from transfers.sensor_transfer import init_sensor
from transfers.waterlevels_transfer import transfer_water_levels
from transfers.well_transfer import (
    transfer_wells,
    transfer_wellscreens,
    cleanup_locations,
)

from transfers.util import timeit, timeit_direct
from transfers.logger import logger, save_log_to_bucket


def erase_and_initalize(session: Session) -> None:
    logger.info("Erasing existing data and initializing lexicon and sensors")
    erase(session)
    lexicon()
    sensor(session)


@timeit
def sensor(session: Session):
    logger.info("Initializing sensors")
    init_sensor(session)


@timeit
def lexicon():
    logger.info("Initializing lexicon")
    init_lexicon()


@timeit
def erase(session: Session):
    logger.info("Erasing existing data")
    from sqlalchemy import text

    with session.bind.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    Base.metadata.drop_all(session.bind)
    logger.info("Recreating tables")
    Base.metadata.create_all(session.bind)


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


@timeit
def transfer_all(sess, limit=100):
    message("STARTING TRANSFER", new_line_at_top=False)
    erase_and_initalize(sess)

    message("TRANSFERRING WELLS")
    timeit_direct(transfer_wells, sess, limit=limit)
    timeit_direct(transfer_wellscreens, sess)

    """
    Developer's note
    this is a very time consuming operation and the results should 
    be saved to a file for later use.
    """
    message("CLEANING UP LOCATIONS")
    timeit_direct(cleanup_locations, sess)

    message("TRANSFERRING SPRINGS")
    timeit_direct(transfer_springs, sess, limit=limit)

    message("TRANSFERRING PERENNIAL STREAMS")
    timeit_direct(transfer_perennial_stream, sess, limit=limit)

    message("TRANSFERRING EPHEMERAL STREAMS")
    timeit_direct(transfer_ephemeral_stream, sess, limit=limit)

    message("TRANSFERRING METEOROLOGICAL")
    timeit_direct(transfer_met, sess, limit)

    message("TRANSFERRING CONTACTS")
    timeit_direct(transfer_contacts, sess)

    """
    Developer's notes

    When transfering water chemistry data use the qc_type field to indicate
    normal/blanks/duplicates instead of what comes from LU_SampleType. Use
    those values, however, to map to the standard qc_type fields if applicable
    (i.e. not applicable when sample type is "Soil or rock sample" or
    "Precipitation," but is applicable when sample type is "Equipment blank"
    or "Field duplicate")
    """
    message("TRANSFERRING LINK IDS")
    timeit_direct(transfer_link_ids, sess)
    timeit_direct(transfer_link_ids_welldata, sess)

    message("TRANSFERRING GROUPS")
    timeit_direct(transfer_groups, sess)

    message("TRANSFERRING WATER LEVELS")
    timeit_direct(transfer_water_levels, sess)

    message("TRANSFERRING ASSETS")
    timeit_direct(transfer_assets, sess)


def main():
    message("START--------------------------------------")
    limit = int(os.environ.get("TRANSFER_LIMIT", 20))
    with session_ctx() as sess:
        transfer_all(sess, limit=limit)

    # todo: move the log file to a storage bucket
    save_log_to_bucket()
    message("END--------------------------------------")


if __name__ == "__main__":
    main()

# ============= EOF =============================================
