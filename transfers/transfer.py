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

load_dotenv()

from transfers.metrics import Metrics
from transfers.waterlevels_transducer_transfer import (
    transfer_water_levels_pressure,
    transfer_water_levels_acoustic,
)
from sqlalchemy.orm import Session
from core.initializers import init_lexicon, init_parameter, erase_and_rebuild_db
from db.engine import session_ctx

from transfers.group_transfer import transfer_groups
from transfers.link_ids_transfer import transfer_link_ids, transfer_link_ids_welldata
from transfers.contact_transfer import transfer_contacts
from transfers.sensor_transfer import transfer_sensors
from transfers.waterlevels_transfer import transfer_water_levels
from transfers.well_transfer import (
    transfer_wells,
    transfer_wellscreens,
)

from transfers.asset_transfer import transfer_assets
from transfers.util import timeit, timeit_direct
from transfers.logger import logger, save_log_to_bucket


def erase_and_initalize(session: Session) -> None:
    logger.info(
        "Erasing existing data and initializing lexicon, parameter, and sensors"
    )
    erase(session)
    lexicon()
    parameter()


@timeit
def lexicon():
    logger.info("Initializing lexicon")
    init_lexicon()


@timeit
def parameter():
    logger.info("Initializing parameter")
    init_parameter()


@timeit
def erase(session: Session):
    logger.info("Erase and rebuilding database")
    erase_and_rebuild_db(session)


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


@timeit
def transfer_all(sess, limit=100):
    message("STARTING TRANSFER", new_line_at_top=False)
    erase_and_initalize(sess)

    metrics = Metrics()
    message("TRANSFERRING WELLS")

    flags = {
        "TRANSFER_ALL_WELLS": True,
        "TRANSFER_ALL_WELLSCREENS": True,
    }

    results = timeit_direct(transfer_wells, sess, flags=flags, limit=limit)
    metrics.well_metrics(sess, *results)

    message("TRANSFERRING WELL SCREENS")
    results = timeit_direct(transfer_wellscreens, sess)
    metrics.well_screen_metrics(sess, *results)

    message("TRANSFERRING SENSORS")
    results = timeit_direct(transfer_sensors, sess)
    metrics.sensor_metrics(sess, *results)

    # Developer's notes all the metadata for these Things are not defined in the models/schemas yet'
    # message("TRANSFERRING SPRINGS")
    # timeit_direct(transfer_springs, sess, limit=limit)
    #
    # message("TRANSFERRING PERENNIAL STREAMS")
    # timeit_direct(transfer_perennial_stream, sess, limit=limit)
    #
    # message("TRANSFERRING EPHEMERAL STREAMS")
    # timeit_direct(transfer_ephemeral_stream, sess, limit=limit)
    #
    # message("TRANSFERRING METEOROLOGICAL")
    # timeit_direct(transfer_met, sess, limit)

    message("TRANSFERRING CONTACTS")
    results = timeit_direct(transfer_contacts, sess)
    metrics.contact_metrics(sess, *results)

    message("TRANSFERRING WATER LEVELS")
    results = timeit_direct(transfer_water_levels, sess)
    metrics.water_level_metrics(sess, *results)

    message("TRANSFERRING WATER LEVELS PRESSURE")
    results = timeit_direct(transfer_water_levels_pressure, sess)
    metrics.pressure_metrics(sess, *results)

    message("TRANSFERRING WATER LEVELS ACOUSTIC")
    results = timeit_direct(transfer_water_levels_acoustic, sess)
    metrics.acoustic_metrics(sess, *results)

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

    message("TRANSFERRING ASSETS")
    timeit_direct(transfer_assets, sess)


def transfer_debugging(sess, limit=100):
    message("STARTING TRANSFER DEBUG", new_line_at_top=False)

    if int(os.environ.get("ERASE_AND_REBUILD", 0)):
        erase_and_initalize(sess)

    metrics = Metrics()
    message("TRANSFERRING WELLS")

    flags = {"TRANSFER_ALL_WELLS": True}

    results = timeit_direct(transfer_wells, sess, flags=flags, limit=limit)
    metrics.well_metrics(sess, *results)

    message("TRANSFERRING WELL SCREENS")
    results = timeit_direct(transfer_wellscreens, sess)
    metrics.well_screen_metrics(sess, *results)

    # message("TRANSFERRING SENSORS")
    # results = timeit_direct(transfer_sensors, sess)
    # metrics.sensor_metrics(sess, *results)

    # Developer's notes all the metadata for these Things are not defined in the models/schemas yet'
    # message("TRANSFERRING SPRINGS")
    # timeit_direct(transfer_springs, sess, limit=limit)
    #
    # message("TRANSFERRING PERENNIAL STREAMS")
    # timeit_direct(transfer_perennial_stream, sess, limit=limit)
    #
    # message("TRANSFERRING EPHEMERAL STREAMS")
    # timeit_direct(transfer_ephemeral_stream, sess, limit=limit)
    #
    # message("TRANSFERRING METEOROLOGICAL")
    # timeit_direct(transfer_met, sess, limit)

    # message("TRANSFERRING CONTACTS")
    # results = timeit_direct(transfer_contacts, sess)
    # metrics.contact_metrics(sess, *results)
    #
    # message("TRANSFERRING WATER LEVELS")
    # results = timeit_direct(transfer_water_levels, sess)
    # metrics.water_level_metrics(sess, *results)

    # message("TRANSFERRING WATER LEVELS PRESSURE")
    # results = timeit_direct(transfer_water_levels_pressure, sess)
    # metrics.pressure_metrics(sess, *results)

    # message("TRANSFERRING WATER LEVELS ACOUSTIC")
    # results = timeit_direct(transfer_water_levels_acoustic, sess)
    # metrics.acoustic_metrics(sess, *results)

    """
    Developer's notes

    When transfering water chemistry data use the qc_type field to indicate
    normal/blanks/duplicates instead of what comes from LU_SampleType. Use
    those values, however, to map to the standard qc_type fields if applicable
    (i.e. not applicable when sample type is "Soil or rock sample" or
    "Precipitation," but is applicable when sample type is "Equipment blank"
    or "Field duplicate")
    """
    # message("TRANSFERRING LINK IDS")
    # timeit_direct(transfer_link_ids, sess)
    # timeit_direct(transfer_link_ids_welldata, sess)

    # message("TRANSFERRING GROUPS")
    # timeit_direct(transfer_groups, sess)

    # message("TRANSFERRING WATER LEVELS ACOUSTIC")
    # timeit_direct(transfer_water_levels_acoustic, sess)
    # message("TRANSFERRING ASSETS")
    # timeit_direct(transfer_assets, sess)


def main():
    message("START--------------------------------------")
    limit = int(os.environ.get("TRANSFER_LIMIT", 1000))
    with session_ctx() as sess:
        if int(os.environ.get("TRANSFER_DEBUG", 0)):
            transfer_debugging(sess, limit=limit)
        else:
            transfer_all(sess, limit=limit)

    # todo: move the log file to a storage bucket
    save_log_to_bucket()
    message("END--------------------------------------")


if __name__ == "__main__":
    main()

# ============= EOF =============================================
