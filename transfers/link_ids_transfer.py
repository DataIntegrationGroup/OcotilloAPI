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
    log,
    extract_organization,
    read_csv,
)


def transfer_link_ids_welldata(session):
    ldf = read_csv("welldata.csv")

    ldf = filter_to_valid_point_ids(session, ldf)

    for i, row in enumerate(ldf.itertuples()):

        # RULE: exclude rows where both ids are null
        if pd.isna(row.OSEWellID) and pd.isna(row.OSEWelltagID):
            log(row, "Both OSEWellID and OSEWelltagID are null")
            continue

        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        if thing is None:
            log(row, "Thing not found")
            continue

        for aid, klass, regex in (
            (row.OSEWellID, "OSEPOD", r"^[A-Z]{1,2}-\d{5,6}"),
            (
                row.OSEWelltagID,
                "OSEWellTagID",
                r"",
            ),  # TODO: need to figure out regex for this field
        ):
            if pd.isna(aid):
                log(row, f"{klass} is null")
                continue

            # RULE: exclude any id that == 'X', '?'
            if aid.strip().lower() in ("x", "?", "exempt"):
                log(row, f'{klass} is "X", "?", or "exempt", id={aid}')
                continue

            if regex and not re.match(regex, aid):
                log(row, f"{klass} id does not match regex {regex}, id={aid}")
                continue

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

    print("adding link id: ", link_id)
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
        log(row, f"alternate id {site_id} is not a valid USGS site id")
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
        log(row, f"alternate id {alternate_id} is not a valid PLSS id")
        return
    link_id.alternate_id = alternate_id
    link_id.alternate_organization = "PLSS"
    session.add(link_id)


def transfer_link_ids(session, site_type="GW"):
    ldf = read_csv("location2.csv")
    ldf = ldf[ldf["SiteType"] == site_type]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    # ldf = ldf[ldf["AlternateSiteID"].notna()]

    ldf = filter_to_valid_point_ids(session, ldf)

    for i, row in enumerate(ldf.itertuples()):
        thing = session.query(Thing).where(Thing.name == row.PointID).first()
        if thing is None:
            # TODO: lets make a sweet function for flagging issues
            # print(f"Thing with PointID {row.PointID} not foaund. Skipping link id.")
            continue
        print(
            f"Processing PointID: {row.PointID}, Thing ID: {thing.id}, a={row.AlternateSiteID}, "
            f"b={row.AlternateSiteID2}"
        )
        add_link_alternate_site_id(session, row, thing)
        # add_link_site_id(session, row, thing)
        # add_link_plss(session, row, thing)

        # not clear what alternate_id2 is for, or what it maps to
        # add_link_alternate_site_id2(session, row, thing)

        session.commit()


# ============= EOF =============================================
