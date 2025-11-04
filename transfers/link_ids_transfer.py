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
import re

import pandas as pd

from db import Thing, ThingIdLink
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    extract_organization,
    read_csv,
    replace_nans,
    chunk_by_size,
)


def transfer_link_ids_welldata(session):
    ldf = read_csv("WellData", dtype={"OSEWelltagID": str})

    ldf = filter_to_valid_point_ids(session, ldf)

    for chunk in chunk_by_size(ldf, 100):
        things = (
            session.query(Thing).filter(Thing.name.in_(chunk.PointID.tolist())).all()
        )
        for row in chunk.itertuples():
            # RULE: exclude rows where both ids are null
            if pd.isna(row.OSEWellID) and pd.isna(row.OSEWelltagID):
                # logger.warning(
                #     f"Both OSEWellID and OSEWelltagID are null for {row.PointID}"
                # )
                continue

            thing = next((l for l in things if l.name == row.PointID), None)
            if thing is None:
                logger.warning(
                    f"Thing not found forPointID {row.PointID}. Skipping link ids."
                )
                continue

            for aid, klass, regex in (
                (row.OSEWellID, "OSEPOD", r"^[A-Z]{1,3}-\d{3,6}"),
                (
                    row.OSEWelltagID,
                    "OSEWellTagID",
                    r"",
                ),  # TODO: need to figure out regex for this field
            ):
                if pd.isna(aid):
                    # logger.warning(f"{klass} is null for {row.PointID}")
                    continue

                # RULE: exclude any id that == 'X', '?'
                if aid.strip().lower() in ("x", "?", "exempt"):
                    logger.critical(
                        f'{klass} is "X", "?", or "exempt", id={aid} for {row.PointID}'
                    )
                    continue

                if regex and not re.match(regex, aid):
                    logger.critical(
                        f"{klass} id does not match regex {regex}, id={aid} for {row.PointID}"
                    )
                    continue

                # TODO: add guards for null values
                link_id = ThingIdLink()
                link_id.thing = thing
                link_id.relation = klass
                link_id.alternate_id = aid
                link_id.alternate_organization = "NMOSE"

                # does link_id need a class  e.g.
                # link_id.alternate_id_class = klass

                session.add(link_id)
        session.commit()


def add_link_alternate_site_id(session, row, thing):
    if not row.AlternateSiteID:
        return

    link_id = ThingIdLink()
    link_id.thing = thing
    link_id.relation = "same_as"
    link_id.alternate_id = row.AlternateSiteID

    link_id.alternate_organization = extract_organization(str(row.AlternateSiteID))

    # logger.info(f"adding link id: {row.PointID}")
    session.add(link_id)


def add_link_site_id(session, row, thing):
    if not row.SiteID:
        return

    link_id = ThingIdLink()
    link_id.thing = thing
    link_id.relation = "same_as"

    site_id = row.SiteID.strip()
    if not re.match(r"^\d{15}$", site_id):
        # TODO: lets make a sweet function for flagging issues
        # flag for interrogation
        logger.critical(
            f"{row.PointID} alternate id {site_id} is not a valid USGS site id"
        )
        return

    link_id.alternate_id = row.SiteID
    link_id.alternate_organization = "USGS"
    session.add(link_id)


def add_link_plss(session, row, thing):

    township = row.Township
    township_direction = row.TownshipDirection
    _range = row.Range
    range_direction = row.RangeDirection
    section = row.Section
    section_direction = row.SectionDirection

    if not township or not _range or not section:
        return

    link_id = ThingIdLink()
    link_id.thing = thing
    link_id.relation = "same_as"
    link_id.alternate_organization = "PLSS"

    alternate_id = f"T{township}{township_direction}.R{_range}{range_direction}.S{section}{section_direction}"
    if not re.match(r"T\d{1,3}.R\d{1,3}.S\d{1,3}", alternate_id):
        # flag for interrogation
        logger.warning(f"alternate id {alternate_id} is not a valid PLSS")
        return
    link_id.alternate_id = alternate_id
    link_id.alternate_organization = "PLSS"
    session.add(link_id)


def transfer_link_ids(session, site_type="GW"):
    ldf = read_csv("Location")
    ldf = ldf[ldf["SiteType"] == site_type]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    ldf = replace_nans(ldf)

    ldf = filter_to_valid_point_ids(session, ldf)
    for chunk in chunk_by_size(ldf, 100):
        locations = (
            session.query(Thing).filter(Thing.name.in_(chunk.PointID.tolist())).all()
        )
        for row in chunk.itertuples():
            thing = next((l for l in locations if l.name == row.PointID), None)
            if thing is None:
                logger.warning(
                    f"Thing with PointID {row.PointID} not found. Skipping link id."
                )
                continue
            logger.info(
                f"Processing PointID: {row.PointID}, Thing ID: {thing.id}, AlternateSiteID={row.AlternateSiteID}, "
                f"AlternateSiteID2={row.AlternateSiteID2}"
            )
            add_link_alternate_site_id(session, row, thing)
        session.commit()

    # for i, row in enumerate(ldf.itertuples()):
    #     thing = session.query(Thing).where(Thing.name == row.PointID).first()
    #     if thing is None:
    #         logger.warning(
    #             f"Thing with PointID {row.PointID} not found. Skipping link id."
    #         )
    #         continue
    #     logger.info(
    #         f"Processing PointID: {row.PointID}, Thing ID: {thing.id}, AlternateSiteID={row.AlternateSiteID}, "
    #         f"AlternateSiteID2={row.AlternateSiteID2}"
    #     )
    #     add_link_alternate_site_id(session, row, thing)
    #     # add_link_site_id(session, row, thing)
    #     # add_link_plss(session, row, thing)
    #
    #     # not clear what alternate_id2 is for, or what it maps to
    #     # add_link_alternate_site_id2(session, row, thing)
    #     if i and not i % 25:
    #         session.commit()
    #         session.flush()
    #
    # session.commit()


# ============= EOF =============================================
