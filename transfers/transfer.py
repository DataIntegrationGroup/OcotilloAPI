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

from db.engine import session_ctx
from services.util import get_bool_env
from transfers.aquifer_system_transfer import transfer_aquifer_systems
from transfers.geologic_formation_transfer import transfer_geologic_formations
from transfers.permissions_transfer import transfer_permissions
from transfers.stratigraphy_transfer import transfer_stratigraphy

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
from transfers.contact_transfer import ContactTransfer
from transfers.sensor_transfer import SensorTransferer
from transfers.waterlevels_transfer import WaterLevelTransferer
from transfers.well_transfer import WellTransferer, WellScreenTransferer

from transfers.asset_transfer import AssetTransferer
from transfers.util import timeit
from transfers.logger import logger, save_log_to_bucket


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


@timeit
def transfer_all(metrics, limit=100):
    message("STARTING TRANSFER", new_line_at_top=False)
    if get_bool_env("ERASE_AND_REBUILD", False):
        logger.info("Erase and rebuilding database")
        erase_and_rebuild_db()

    flags = {"TRANSFER_ALL_WELLS": True, "LIMIT": limit}  # not currently used

    with session_ctx() as session:
        transfer_aquifer_systems(session, limit=limit)
        transfer_geologic_formations(session, limit=limit)

    message("TRANSFERRING WELLS")
    results = _execute_transfer(WellTransferer, flags=flags)
    metrics.well_metrics(*results)

    transfer_screens = get_bool_env("TRANSFER_WELL_SCREENS", True)
    transfer_sensors = get_bool_env("TRANSFER_SENSORS", True)
    transfer_contacts = get_bool_env("TRANSFER_CONTACTS", True)
    transfer_waterlevels = get_bool_env("TRANSFER_WATERLEVELS", True)
    transfer_pressure = get_bool_env("TRANSFER_WATERLEVELS_PRESSURE", True)
    transfer_acoustic = get_bool_env("TRANSFER_WATERLEVELS_ACOUSTIC", True)
    transfer_link_ids = get_bool_env("TRANSFER_LINK_IDS", True)
    transfer_groups = get_bool_env("TRANSFER_GROUPS", True)
    transfer_assets = get_bool_env("TRANSFER_ASSETS", True)

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

    if transfer_contacts:
        message("TRANSFERRING CONTACTS")
        results = _execute_transfer(ContactTransfer, flags=flags)
        metrics.contact_metrics(*results)

    message("TRANSFERRING PERMISSIONS")
    with session_ctx() as session:
        transfer_permissions(session)

    message("TRANSFERRING STRATIGRAPY")
    with session_ctx() as session:
        results = transfer_stratigraphy(session, limit=limit)
        metrics.stratigraphy_metrics(*results)

    if transfer_waterlevels:
        message("TRANSFERRING WATER LEVELS")
        results = _execute_transfer(WaterLevelTransferer, flags=flags)
        metrics.water_level_metrics(*results)

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


def _execute_transfer(klass, flags: dict = None):
    transferer = klass(flags=flags)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


def main():
    message("START--------------------------------------")
    limit = int(os.getenv("TRANSFER_LIMIT", 1000))
    metrics = Metrics()

    transfer_all(metrics, limit=limit)

    metrics.close()
    metrics.save_to_storage_bucket()
    # todo: move the log file to a storage bucket
    save_log_to_bucket()
    message("END--------------------------------------")


if __name__ == "__main__":
    main()
# ============= EOF =============================================
