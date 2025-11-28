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
)
from transfers.well_transfer import WellChunkTransferer


class LinkIdsWellDataTransferer(WellChunkTransferer):
    source_table = "WellData"
    source_dtypes = {"OSEWellID": str, "OSEWelltagID": str}

    def _chunk_step(self, session, dr, i, row, db_item):
        if pd.isna(row.OSEWellID) and pd.isna(row.OSEWelltagID):
            return

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
            print("aid", aid, type(aid))
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
            link_id.thing = db_item
            link_id.relation = klass
            link_id.alternate_id = aid
            link_id.alternate_organization = "NMOSE"

            # does link_id need a class  e.g.
            # link_id.alternate_id_class = klass

            session.add(link_id)


class LinkIdsLocationDataTransferer(WellChunkTransferer):
    source_table = "Location"
    site_type = "GW"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self._plss_regex = re.compile(
            r"^T\d{1,3}[NS]\.R\d{1,3}[EW]\.S(?:[1-9]|[12]\d|3[0-6])(?:\.\d{1,5})?$"
        )
        self._usgs_regex = re.compile(r"^\d{15}$")

    def _get_dfs(self):
        input_df = read_csv(
            self.source_table,
            {
                "SiteID": str,
                "Township": str,
                "TownshipDirection": str,
                "Range": str,
                "RangeDirection": str,
                "SectionQuarters": str,
            },
        )

        ldf = input_df[input_df["SiteType"] == self.site_type]
        ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
        ldf = replace_nans(ldf)
        cleaned_df = filter_to_valid_point_ids(ldf)
        return input_df, cleaned_df

    def _chunk_step(self, session, df, i, row, db_item):
        logger.info(
            f"Processing PointID: {row.PointID}, "
            f"Thing ID: {db_item.id}, "
            f"AlternateSiteID={row.AlternateSiteID}, "
            f"AlternateSiteID2={row.AlternateSiteID2}"
        )
        for func in (
            self._add_link_alternate_site_id,
            self._add_link_site_id,
            self._add_link_plss,
        ):
            link = func(row, db_item)
            if link:
                session.add(link)

    def _add_link_alternate_site_id(self, row: pd.Series, thing: Thing):
        if not row.AlternateSiteID:
            return

        return _make_thing_id_link(
            thing, row.AlternateSiteID, extract_organization(str(row.AlternateSiteID))
        )

    def _add_link_site_id(self, row, thing):
        if not row.SiteID:
            return

        site_id = row.SiteID.strip()
        if not self._usgs_regex.match(site_id):
            self._capture_error(
                row.PointID, f"{site_id} is not a valid USGS site id", "SiteID"
            )
            logger.critical(
                f"{row.PointID} alternate id {site_id} is not a valid USGS site id"
            )
            return

        return _make_thing_id_link(thing, row.SiteID, "USGS")

    def _add_link_plss(self, row, thing):
        township = row.Township
        township_direction = row.TownshipDirection
        _range = row.Range
        range_direction = row.RangeDirection
        section = row.SectionQuarters
        if not township or not _range or not section:
            return

        alternate_id = (
            f"T{township}{township_direction}.R{_range}{range_direction}.S{section}"
        )
        if not self._plss_regex.match(alternate_id):
            self._capture_error(
                row.PointID,
                f"{alternate_id} is not a valid PLSS",
                "Township, TownshipDirection, Range, RangeDirection, Section, SectionDirection",
            )

            logger.critical(f"alternate id {alternate_id} is not a valid PLSS")
            return

        return _make_thing_id_link(thing, alternate_id, "PLSS")


def _make_thing_id_link(
    thing, alternate_id, alternate_organization, relation="same_as"
):
    return ThingIdLink(
        thing=thing,
        relation=relation,
        alternate_id=alternate_id,
        alternate_organization=alternate_organization,
    )


# ============= EOF =============================================
