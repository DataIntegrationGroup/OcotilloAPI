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

from transfers.waterlevels_transducer_transfer import (
    WaterLevelsContinuousPressureTransferer,
    WaterLevelsContinuousAcousticTransferer,
)

from transfers.metrics import Metrics
from core.initializers import erase_and_rebuild_db

from transfers.group_transfer import ProjectGroupTransferer
from transfers.link_ids_transfer import (
    LinkIdsWellDataTransferer,
    LinkIdsLocationDataTransferer,
)
from transfers.contact_transfer import transfer_contacts
from transfers.sensor_transfer import SensorTransferer
from transfers.waterlevels_transfer import WaterLevelTransferer
from transfers.well_transfer import WellTransferer, WellScreenTransferer

from transfers.asset_transfer import AssetTransferer
from transfers.util import timeit, timeit_direct
from transfers.logger import logger, save_log_to_bucket


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


@timeit
def transfer_all(sess, metrics, limit=100):
    message("STARTING TRANSFER", new_line_at_top=False)

    logger.info("Erase and rebuilding database")
    erase_and_rebuild_db()

    message("TRANSFERRING WELLS")

    flags = {
        "TRANSFER_ALL_WELLS": True,
        "TRANSFER_ALL_WELLSCREENS": True,
        "LIMIT": limit,
    }

    results = _execute_transfer(WellTransferer, flags=flags)
    metrics.well_metrics(sess, *results)

    message("TRANSFERRING WELL SCREENS")
    results = _execute_transfer(WellScreenTransferer, flags=flags)
    metrics.well_screen_metrics(sess, *results)

    message("TRANSFERRING SENSORS")
    results = _execute_transfer(SensorTransferer, flags=flags)
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
    results = _execute_transfer(WaterLevelTransferer, flags=flags)
    metrics.water_level_metrics(*results)

    # message("TRANSFERRING WATER LEVELS PRESSURE")
    # results = timeit_direct(transfer_water_levels_pressure, sess)
    # metrics.pressure_metrics(sess, *results)
    #
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
    message("TRANSFERRING LINK IDS")
    results = _execute_transfer(LinkIdsWellDataTransferer, flags=flags)
    metrics.welldata_link_ids_metrics(*results)
    results = _execute_transfer(LinkIdsLocationDataTransferer, flags=flags)
    metrics.location_link_ids_metrics(*results)

    message("TRANSFERRING GROUPS")
    results = _execute_transfer(ProjectGroupTransferer, flags=flags)
    metrics.group_metrics(*results)

    message("TRANSFERRING ASSETS")
    results = _execute_transfer(AssetTransferer, flags=flags)
    metrics.asset_metrics(*results)


def _execute_transfer(klass, flags: dict = None):
    transferer = klass(flags=flags)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


def transfer_debugging(metrics, limit=100):
    message("STARTING TRANSFER DEBUG", new_line_at_top=False)

    if int(os.environ.get("ERASE_AND_REBUILD", 0)):
        logger.info("Erase and rebuilding database")
        erase_and_rebuild_db()

    flags = {"TRANSFER_ALL_WELLS": True, "LIMIT": limit}  # not currently used

    message("TRANSFERRING WELLS")
    results = _execute_transfer(WellTransferer, flags=flags)
    metrics.well_metrics(*results)

    transfer_screens = False
    transfer_sensors = True
    transfer_pressure = True
    transfer_acoustic = True
    transfer_link_ids = False
    transfer_groups = False
    transfer_assets = False

    if transfer_screens:
        message("TRANSFERRING WELL SCREENS")
        results = _execute_transfer(WellScreenTransferer, flags=flags)
        metrics.well_screen_metrics(*results)

    if transfer_sensors:
        message("TRANSFERRING SENSORS")
        results = _execute_transfer(SensorTransferer, flags=flags)
        metrics.sensor_metrics(*results)

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
    # results = _execute_transfer(WaterLevelTransferer, flags=flags)
    # metrics.water_level_metrics(*results)

    if transfer_pressure:
        message("TRANSFERRING WATER LEVELS PRESSURE")
        results = _execute_transfer(
            WaterLevelsContinuousPressureTransferer, flags=flags
        )
        metrics.pressure_metrics(*results)

    if transfer_acoustic:
        message("TRANSFERRING WATER LEVELS ACOUSTIC")
        results = _execute_transfer(
            WaterLevelsContinuousAcousticTransferer, flags=flags
        )
        metrics.acoustic_metrics(*results)

    if transfer_link_ids:
        message("TRANSFERRING LINK IDS")
        results = _execute_transfer(LinkIdsWellDataTransferer, flags=flags)
        metrics.welldata_link_ids_metrics(*results)
        results = _execute_transfer(LinkIdsLocationDataTransferer, flags=flags)
        metrics.location_link_ids_metrics(*results)

    if transfer_groups:
        message("TRANSFERRING GROUPS")
        results = _execute_transfer(ProjectGroupTransferer, flags=flags)
        metrics.group_metrics(*results)

    if transfer_assets:
        message("TRANSFERRING ASSETS")
        results = _execute_transfer(AssetTransferer, flags=flags)
        metrics.asset_metrics(*results)


def main():
    message("START--------------------------------------")
    limit = int(os.getenv("TRANSFER_LIMIT", 1000))
    metrics = Metrics()

    if int(os.getenv("TRANSFER_DEBUG", 0)):
        transfer_debugging(metrics, limit=limit)
    else:
        transfer_all(metrics, limit=limit)

    metrics.close()
    metrics.save_to_storage_bucket()
    # todo: move the log file to a storage bucket
    save_log_to_bucket()
    message("END--------------------------------------")


if __name__ == "__main__":
    main()

# ============= EOF =============================================
