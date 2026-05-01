"""
One-time data migration: populate NMBGMR site names as ThingIdLink records.

The legacy Location.csv has a SiteNames column with the human-readable site
name assigned by NMBGMR (e.g. "Zwager domestic", "Pendaries Village Well #1").
This value was never transferred into the ThingIdLink table, so the site_name
property on Thing always returned None.

This script is idempotent: it skips any (thing_id, NMBGMR, alternate_id) row
that already exists.

Usage (from repo root, with venv active):
    python -m transfers.migrate_nmbgmr_site_names
"""

import logging

import pandas as pd
from sqlalchemy import insert, select, tuple_

from db import Thing, ThingIdLink
from db.engine import session_ctx
from transfers.util import get_transfers_data_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ALTERNATE_ORGANIZATION = "NMBGMR"
RELATION = "same_as"
RELEASE_STATUS = "public"


def run():
    csv_path = get_transfers_data_path("nma_csv_cache/Location.csv")
    logger.info("Reading %s", csv_path)

    df = pd.read_csv(csv_path, dtype=str, usecols=["LocationId", "SiteNames"])
    df = df[
        df["SiteNames"].notna()
        & (df["SiteNames"] != "NULL")
        & (df["SiteNames"].str.strip() != "")
    ].copy()
    df["SiteNames"] = df["SiteNames"].str.strip()
    logger.info("%d rows with a non-empty SiteNames value", len(df))

    with session_ctx() as session:
        # Match on LocationId -> nma_pk_location rather than PointID -> name.
        # PointID is not unique across all Location rows; LocationId (the UUID
        # primary key from NM_Aquifer) has higher fidelity. Suggested by
        # jacob-a-brown in PR #668.
        location_ids = df["LocationId"].tolist()
        thing_id_by_location_id: dict[str, int] = {
            location_id: thing_id
            for location_id, thing_id in session.execute(
                select(Thing.nma_pk_location, Thing.id).where(
                    Thing.nma_pk_location.in_(location_ids)
                )
            ).all()
        }
        logger.info(
            "%d / %d LocationIds matched a Thing in the database",
            len(thing_id_by_location_id),
            len(df),
        )

        # Build candidate rows.
        candidates: list[dict] = []
        for row in df.itertuples(index=False):
            thing_id = thing_id_by_location_id.get(row.LocationId)
            if thing_id is None:
                continue
            candidates.append(
                {
                    "thing_id": thing_id,
                    "relation": RELATION,
                    "alternate_id": row.SiteNames,
                    "alternate_organization": ALTERNATE_ORGANIZATION,
                    "release_status": RELEASE_STATUS,
                }
            )

        # Skip rows that already exist (idempotent).
        existing_keys: set[tuple[int, str, str]] = set(
            session.execute(
                select(
                    ThingIdLink.thing_id,
                    ThingIdLink.alternate_organization,
                    ThingIdLink.alternate_id,
                ).where(ThingIdLink.alternate_organization == ALTERNATE_ORGANIZATION)
            ).all()
        )
        logger.info(
            "%d NMBGMR ThingIdLink rows already in the database", len(existing_keys)
        )

        rows_to_insert = [
            r
            for r in candidates
            if (r["thing_id"], r["alternate_organization"], r["alternate_id"])
            not in existing_keys
        ]
        logger.info("%d new rows to insert", len(rows_to_insert))

        if not rows_to_insert:
            logger.info("Nothing to do.")
            return

        session.execute(insert(ThingIdLink), rows_to_insert)
        session.commit()
        logger.info("Done. Inserted %d NMBGMR site name links.", len(rows_to_insert))


if __name__ == "__main__":
    run()
