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
import time
from types import SimpleNamespace

from pandas import isna
from pydantic import ValidationError
from sqlalchemy import insert
from sqlalchemy.orm import Session

from db import LocationThingAssociation, Location, Thing, Notes, DataProvenance
from transfers.logger import logger
from transfers.util import (
    make_location,
    make_location_data_provenance,
    read_csv,
    replace_nans,
)

_LOCATION_DF_CACHE = None


def _get_location_df():
    global _LOCATION_DF_CACHE
    # transfer_thing is executed in a session-scoped, non-threaded transfer flow.
    # Keep a simple module-level cache and avoid lock complexity here.
    if _LOCATION_DF_CACHE is None:
        df = read_csv("Location")
        _LOCATION_DF_CACHE = replace_nans(df)
    return _LOCATION_DF_CACHE


def transfer_thing(
    session: Session,
    site_type: str,
    make_payload,
    limit=None,
    pointids: list[str] | None = None,
) -> None:
    ldf = _get_location_df()
    ldf = ldf[ldf["SiteType"] == site_type]
    ldf = ldf[ldf["Easting"].notna() & ldf["Northing"].notna()]
    if pointids:
        normalized_pointids = ldf["PointID"].map(
            lambda value: str(value).strip().upper()
        )
        ldf = ldf[normalized_pointids.isin(set(pointids))]
        if ldf.empty:
            logger.info(
                "No matching PointIDs for site type %s in scoped run; skipping",
                site_type,
            )
            return

    # Pre-compute duplicate PointIDs once to avoid O(n^2) filtering in the loop.
    duplicate_mask = ldf["PointID"].duplicated(keep=False)
    duplicate_pointids = set(ldf.loc[duplicate_mask, "PointID"])
    if duplicate_pointids:
        logger.warning(
            "Found %s duplicate PointID values for site type %s; these will be skipped.",
            len(duplicate_pointids),
            site_type,
        )

    n = len(ldf)
    start_time = time.time()
    batch_size = 500

    logger.info("Starting transfer: Things (%s) [%s rows]", site_type, n)
    cached_elevations = {}
    prepared_rows: list[dict] = []
    skipped_count = 0

    for i, row in enumerate(ldf.itertuples(index=False)):
        pointid = row.PointID
        if pointid in duplicate_pointids:
            logger.critical("PointID %s has duplicate records. Skipping.", pointid)
            skipped_count += 1
            continue

        if limit is not None and limit > 0 and i >= limit:
            logger.warning(f"Reached limit of {limit} rows. Stopping migration.")
            break

        if i and not i % 25:
            logger.info(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )

        try:
            location, elevation_method, location_notes = make_location(
                row, cached_elevations
            )
            payload = make_payload(row)
            prepared_rows.append(
                {
                    "row": row,
                    "location_row": {
                        "nma_pk_location": location.nma_pk_location,
                        "description": location.description,
                        "point": location.point,
                        "elevation": location.elevation,
                        "release_status": location.release_status,
                        "nma_date_created": location.nma_date_created,
                        "nma_site_date": location.nma_site_date,
                        "nma_location_notes": location.nma_location_notes,
                        "nma_coordinate_notes": location.nma_coordinate_notes,
                        "nma_data_reliability": location.nma_data_reliability,
                    },
                    "location_notes": location_notes,
                    "elevation_method": elevation_method,
                    "thing_row": {
                        "name": payload["name"],
                        "thing_type": payload["thing_type"],
                        "release_status": payload["release_status"],
                        "nma_pk_location": row.LocationId,
                    },
                }
            )
        except ValidationError as e:
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
            skipped_count += 1
        except Exception as e:
            logger.critical(f"Error creating location for {row.PointID}: {e}")
            skipped_count += 1
            continue

    created_count = 0
    for start in range(0, len(prepared_rows), batch_size):
        chunk = prepared_rows[start : start + batch_size]
        if not chunk:
            continue

        location_rows = [item["location_row"] for item in chunk]
        inserted_locations = session.execute(
            insert(Location).returning(Location.id, Location.nma_pk_location),
            location_rows,
        ).all()
        location_id_by_nma_pk = {
            nma_pk: loc_id for loc_id, nma_pk in inserted_locations
        }

        thing_rows = [item["thing_row"] for item in chunk]
        inserted_things = session.execute(
            insert(Thing).returning(Thing.id, Thing.nma_pk_location),
            thing_rows,
        ).all()
        thing_id_by_nma_pk = {nma_pk: thing_id for thing_id, nma_pk in inserted_things}

        notes_rows: list[dict] = []
        provenance_rows: list[dict] = []
        assoc_rows: list[dict] = []

        for item in chunk:
            nma_pk_location = item["thing_row"]["nma_pk_location"]
            location_id = location_id_by_nma_pk.get(nma_pk_location)
            thing_id = thing_id_by_nma_pk.get(nma_pk_location)

            if location_id is None or thing_id is None:
                logger.critical(
                    "Failed to resolve inserted IDs for nma_pk_location=%s; skipping associations",
                    nma_pk_location,
                )
                skipped_count += 1
                continue

            assoc_rows.append({"location_id": location_id, "thing_id": thing_id})

            for note_type, note_content in item["location_notes"].items():
                if not isna(note_content):
                    notes_rows.append(
                        {
                            "target_id": location_id,
                            "target_table": "location",
                            "note_type": note_type,
                            "content": note_content,
                            "release_status": "draft",
                        }
                    )

            # Reuse existing provenance mapper by passing an object with .id.
            location_stub = SimpleNamespace(id=location_id)
            data_provenances = make_location_data_provenance(
                item["row"], location_stub, item["elevation_method"]
            )
            for dp in data_provenances:
                provenance_rows.append(
                    {
                        "target_id": dp.target_id,
                        "target_table": dp.target_table,
                        "field_name": dp.field_name,
                        "origin_type": dp.origin_type,
                        "origin_source": dp.origin_source,
                        "collection_method": dp.collection_method,
                        "accuracy_value": dp.accuracy_value,
                        "accuracy_unit": dp.accuracy_unit,
                        "release_status": dp.release_status or "draft",
                    }
                )

        if notes_rows:
            session.execute(insert(Notes), notes_rows)
        if provenance_rows:
            session.execute(insert(DataProvenance), provenance_rows)
        if assoc_rows:
            session.execute(insert(LocationThingAssociation), assoc_rows)
            created_count += len(assoc_rows)

    session.commit()
    logger.info(
        "Things transfer summary (%s): created=%s skipped=%s total_candidates=%s",
        site_type,
        created_count,
        skipped_count,
        n,
    )
    logger.info("Completed transfer: Things (%s)", site_type)


def _release_status(row) -> str:
    return "public" if row.PublicRelease else "private"


def transfer_springs(session, limit=None, pointids: list[str] | None = None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "spring",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "SP", make_payload, limit, pointids)


def transfer_perennial_streams(session, limit=None, pointids: list[str] | None = None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "perennial stream",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "PS", make_payload, limit, pointids)


def transfer_ephemeral_streams(session, limit=None, pointids: list[str] | None = None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "ephemeral stream",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "ES", make_payload, limit, pointids)


def transfer_met_stations(session, limit=None, pointids: list[str] | None = None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "meteorological station",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "M", make_payload, limit, pointids)


def transfer_rock_sample_locations(
    session, limit=None, pointids: list[str] | None = None
):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "rock sample location",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "R", make_payload, limit, pointids)


def transfer_diversion_of_surface_water(
    session, limit=None, pointids: list[str] | None = None
):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "diversion of surface water, etc.",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "D", make_payload, limit, pointids)


def transfer_lake_pond_reservoir(
    session, limit=None, pointids: list[str] | None = None
):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "lake, pond or reservoir",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "L", make_payload, limit, pointids)


def transfer_soil_gas_sample_locations(
    session, limit=None, pointids: list[str] | None = None
):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "soil gas sample location",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "S", make_payload, limit, pointids)


def transfer_other_site_types(session, limit=None, pointids: list[str] | None = None):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "other",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "OT", make_payload, limit, pointids)


def transfer_outfall_wastewater_return_flow(
    session, limit=None, pointids: list[str] | None = None
):
    def make_payload(row):
        return {
            "name": row.PointID,
            "thing_type": "outfall of wastewater or return flow",
            "release_status": _release_status(row),
        }

    transfer_thing(session, "O", make_payload, limit, pointids)


# ============= EOF =============================================
