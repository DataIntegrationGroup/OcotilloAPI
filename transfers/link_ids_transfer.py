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
from sqlalchemy import insert

from db import Thing, ThingIdLink
from transfers.transferer import chunk_by_size
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
    _ose_wellid_regex = re.compile(r"^[A-Z]{1,3}-\d{3,6}$")

    def _transfer_hook(self, session):
        df = self._get_df_to_iterate()
        for ci, chunk in enumerate(chunk_by_size(df, self.chunk_size)):
            thing_id_by_pointid = {
                name: thing_id
                for name, thing_id in session.query(Thing.name, Thing.id)
                .filter(Thing.name.in_(chunk.PointID.tolist()))
                .all()
            }
            logger.info(
                "Processing LinkIdsWellData chunk %s, %s rows, %s db items",
                ci,
                len(chunk),
                len(thing_id_by_pointid),
            )
            existing_link_keys = _fetch_existing_link_keys(
                session, thing_id_by_pointid.values()
            )

            rows_to_insert: list[dict] = []
            for row in chunk.itertuples(index=False):
                thing_id = thing_id_by_pointid.get(row.PointID)
                if thing_id is None:
                    self._missing_db_item_warning(row)
                    continue

                if pd.isna(row.OSEWellID) and pd.isna(row.OSEWelltagID):
                    continue

                for aid, relation, regex in (
                    (row.OSEWellID, "OSEPOD", self._ose_wellid_regex),
                    (row.OSEWelltagID, "OSEWellTagID", None),
                ):
                    if pd.isna(aid):
                        continue

                    aid_text = str(aid).strip()
                    if not aid_text:
                        continue

                    # RULE: exclude any id that == 'X', '?', or 'exempt'
                    if aid_text.casefold() in ("x", "?", "exempt"):
                        logger.critical(
                            '%s is "X", "?", or "exempt", id=%s for %s',
                            relation,
                            aid_text,
                            row.PointID,
                        )
                        continue

                    if regex and not regex.match(aid_text):
                        logger.critical(
                            "%s id does not match regex %s, id=%s for %s",
                            relation,
                            regex.pattern,
                            aid_text,
                            row.PointID,
                        )
                        continue

                    link_row = {
                        "thing_id": thing_id,
                        "relation": relation,
                        "alternate_id": aid_text,
                        "alternate_organization": "NMOSE",
                    }
                    link_key = _link_row_key(link_row)
                    if link_key in existing_link_keys:
                        continue

                    rows_to_insert.append(link_row)
                    existing_link_keys.add(link_key)

            if rows_to_insert:
                session.execute(insert(ThingIdLink), rows_to_insert)
            session.commit()
            session.expunge_all()


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
        cleaned_df = filter_to_valid_point_ids(ldf, self.pointids)
        return input_df, cleaned_df

    def _transfer_hook(self, session):
        df = self._get_df_to_iterate()
        for ci, chunk in enumerate(chunk_by_size(df, self.chunk_size)):
            thing_id_by_pointid = {
                name: thing_id
                for name, thing_id in session.query(Thing.name, Thing.id)
                .filter(Thing.name.in_(chunk.PointID.tolist()))
                .all()
            }
            logger.info(
                "Processing LinkIdsLocationData chunk %s, %s rows, %s db items",
                ci,
                len(chunk),
                len(thing_id_by_pointid),
            )
            existing_link_keys = _fetch_existing_link_keys(
                session, thing_id_by_pointid.values()
            )

            rows_to_insert: list[dict] = []
            for row in chunk.itertuples(index=False):
                thing_id = thing_id_by_pointid.get(row.PointID)
                if thing_id is None:
                    self._missing_db_item_warning(row)
                    continue

                for func in (
                    self._add_link_alternate_site_id,
                    self._add_link_site_id,
                    self._add_link_plss,
                ):
                    link_row = func(row, thing_id)
                    if link_row:
                        link_key = _link_row_key(link_row)
                        if link_key in existing_link_keys:
                            continue
                        rows_to_insert.append(link_row)
                        existing_link_keys.add(link_key)

            if rows_to_insert:
                session.execute(insert(ThingIdLink), rows_to_insert)
            session.commit()
            session.expunge_all()

    def _chunk_step(self, session, df, i, row, db_item):
        # Kept for compatibility; bulk path uses _transfer_hook.
        for func in (
            self._add_link_alternate_site_id,
            self._add_link_site_id,
            self._add_link_plss,
        ):
            link = func(row, db_item.id)
            if link:
                session.execute(insert(ThingIdLink), [link])

    def _add_link_alternate_site_id(self, row: pd.Series, thing_id: int):
        if not row.AlternateSiteID:
            return

        return _make_thing_id_link(
            thing_id,
            row.AlternateSiteID,
            extract_organization(str(row.AlternateSiteID)),
        )

    def _add_link_site_id(self, row, thing_id: int):
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

        return _make_thing_id_link(thing_id, row.SiteID, "USGS")

    def _add_link_plss(self, row, thing_id: int):
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

        return _make_thing_id_link(thing_id, alternate_id, "PLSS")


def _make_thing_id_link(
    thing_id: int, alternate_id, alternate_organization, relation="same_as"
):
    return {
        "thing_id": thing_id,
        "relation": relation,
        "alternate_id": alternate_id,
        "alternate_organization": alternate_organization,
    }


def _link_row_key(row: dict) -> tuple[int, str, str, str]:
    return (
        row["thing_id"],
        row["relation"],
        row["alternate_id"],
        row["alternate_organization"],
    )


def _fetch_existing_link_keys(session, thing_ids) -> set[tuple[int, str, str, str]]:
    thing_ids = list(set(thing_ids))
    if not thing_ids:
        return set()

    return {
        (thing_id, relation, alternate_id, alternate_organization)
        for thing_id, relation, alternate_id, alternate_organization in session.query(
            ThingIdLink.thing_id,
            ThingIdLink.relation,
            ThingIdLink.alternate_id,
            ThingIdLink.alternate_organization,
        )
        .filter(ThingIdLink.thing_id.in_(thing_ids))
        .all()
    }


# ============= EOF =============================================
