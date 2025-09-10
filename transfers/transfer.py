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
from sqlalchemy.orm import Session

from core.initializers import init_lexicon
from db import Base
from db.engine import session_ctx
from transfers.asset_transfer import transfer_assets_testing
from transfers.group_transfer import transfer_groups
from transfers.link_ids_transfer import transfer_link_ids, transfer_link_ids_welldata
from transfers.contact_transfer import transfer_contacts
from transfers.sensor_transfer import init_sensor
from transfers.waterlevels_transfer import transfer_water_levels

from transfers.well_transfer import transfer_wells, transfer_wellscreens
from transfers.thing_transfer import (
    transfer_springs,
    transfer_perennial_stream,
    transfer_ephemeral_stream,
    transfer_met,
)
from transfers.util import logger


def erase_and_initalize(session: Session) -> None:
    Base.metadata.drop_all(session.bind)
    Base.metadata.create_all(session.bind)

    init_lexicon()
    init_sensor(session)


def main_transfer():
    logger.log("")
    logger.log("Starting transfer\n")

    init = True

    transfer_well_flag = False
    transfer_spring_flag = False
    transfer_perennial_stream_flag = False
    transfer_ephemeral_stream_flag = False
    transfer_met_flag = False
    transfer_contacts_flag = False
    transfer_waterlevels_flag = False
    transfer_link_ids_flag = False
    transfer_assets_flag = False
    transfer_groups_flag = False

    cleanup_wells_flag = False

    limit = 100
    with session_ctx() as sess:
        if init:
            erase_and_initalize(sess)

        if init or transfer_well_flag:
            msg = "*" * 10 + "TRANSFERRING WELLS" + "*" * 10
            logger.info(msg)
            transfer_wells(sess, limit)
            transfer_wellscreens(sess)
            logger.info("")

        if init or transfer_spring_flag:
            msg = "*" * 10 + "TRANSFERRING SPRINGS" + "*" * 10
            logger.info(msg)
            transfer_springs(sess, limit)
            logger.info("")

        if init or transfer_perennial_stream_flag:
            msg = "*" * 10 + "TRANSFERRING PERENNIAL STREAMS" + "*" * 10
            logger.info(msg)
            transfer_perennial_stream(sess, limit)
            logger.info("")

        if init or transfer_ephemeral_stream_flag:
            msg = "*" * 10 + "TRANSFERRING EPHEMERAL STREAMS" + "*" * 10
            logger.info(msg)
            transfer_ephemeral_stream(sess, limit)
            logger.info("")

        if init or transfer_met_flag:
            msg = "*" * 10 + "TRANSFERRING METEOROLOGICAL" + "*" * 10
            logger.info(msg)
            transfer_met(sess, limit)
            logger.info("")

        if init or transfer_contacts_flag:
            msg = "*" * 10 + "TRANSFERRING CONTACTS" + "*" * 10
            logger.info(msg)
            transfer_contacts(sess)
            logger.info("")

        if init or transfer_waterlevels_flag:
            msg = "*" * 10 + "TRANSFERRING WATER LEVELS" + "*" * 10
            logger.info(msg)
            transfer_water_levels(sess)
            logger.info("")

        if init or transfer_link_ids_flag:
            msg = "*" * 10 + "TRANSFERRING LINK IDS" + "*" * 10
            logger.info(msg)
            transfer_link_ids(sess)
            transfer_link_ids_welldata(sess)
            logger.info("")

        if init or transfer_assets_flag:
            msg = "*" * 10 + "TRANSFERRING ASSETS" + "*" * 10
            logger.info(msg)
            transfer_assets_testing(sess)
            logger.info("")

        if init or transfer_groups_flag:
            msg = "*" * 10 + "TRANSFERRING GROUPS" + "*" * 10
            logger.info(msg)
            transfer_groups(sess)
            logger.info("")

        # if init or cleanup_wells_flag:
        #     cleanup_wells(sess)


if __name__ == "__main__":
    main_transfer()

# ============= EOF =============================================
