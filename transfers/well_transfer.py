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
import json
import time
from pydantic import ValidationError
from sqlalchemy import select
from datetime import datetime
from pandas import isna

from db import (
    LocationThingAssociation,
    Thing,
    WellScreen,
    Location,
    WellPurpose,
    WellCasingMaterial,
)
from schemas.thing import CreateWellScreen, CreateWell
from services.gcs_helper import get_storage_bucket
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
from transfers.util import (
    make_location,
    filter_to_valid_point_ids,
    read_csv,
    logger,
    replace_nans,
    filter_by_welldata_datasource,
    lexicon_mapper,
)

ADDED = []


def _get_first_visit_date(row) -> datetime | None:
    first_visit_date = None
    if row.DateCreated and row.SiteDate:
        date_created = datetime.strptime(row.DateCreated, "%Y-%m-%d %H:%M:%S.%f").date()
        site_date = datetime.strptime(row.SiteDate, "%Y-%m-%d %H:%M:%S.%f").date()

        if date_created < site_date:
            first_visit_date = date_created
        else:
            first_visit_date = site_date
    elif row.DateCreated and not row.SiteDate:
        first_visit_date = datetime.strptime(
            row.DateCreated, "%Y-%m-%d %H:%M:%S.%f"
        ).date()
    elif not row.DateCreated and row.SiteDate:
        first_visit_date = datetime.strptime(
            row.SiteDate, "%Y-%m-%d %H:%M:%S.%f"
        ).date()

    return first_visit_date


def _extract_well_purposes(row) -> list[str]:
    cu = row.CurrentUse
    purposes = (
        []
        if isna(cu)
        else [lexicon_mapper.map_value(f"LU_CurrentUse:{cui}") for cui in cu]
    )

    # logger.info(f"well {row.PointID},{cu} has purposes: {purposes}")
    return purposes


def _extract_casing_materials(row) -> list[str]:
    materials = []
    if "pvc" in row.CasingDescription.lower():
        materials.append("PVC")

    if "steel" in row.CasingDescription.lower():
        materials.append("Steel")

    if "concrete" in row.CasingDescription.lower():
        materials.append("Concrete")
    return materials


def transfer_wells(session, limit=0) -> None:
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    ldf = read_csv("Location")
    ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1)
    wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    wdf = replace_nans(wdf)

    # todo: filter Locations by DataSource
    wdf = filter_by_welldata_datasource(wdf)

    n = len(wdf)

    step = 25
    start_time = time.time()
    for i, row in enumerate(wdf.itertuples()):
        pointid = row.PointID
        if wdf[wdf["PointID"] == pointid].shape[0] > 1:
            logger.critical(
                f"transfer_wells. PointID {pointid} has duplicate records. Skipping."
            )
            continue

        if limit and i >= limit:
            logger.info(f"Reached limit of {limit} rows. Stopping migration.")
            break

        if i and not i % step:
            logger.info(
                f"Processing row {i} of {n},  avg rows per second: {step / (time.time() - start_time):.2f}"
            )
            start_time = time.time()
            try:
                session.commit()
            except Exception as e:
                logger.critical(f"Error committing wells. {e}")
                session.rollback()
                continue

        try:
            location = make_location(row)
            session.add(location)
        except Exception as e:
            session.rollback()
            logger.critical(f"Error making location for {row.PointID}: {e}")
            continue

        try:
            first_visit_date = _get_first_visit_date(row)
            well_purposes = [] if isna(row.CurrentUse) else _extract_well_purposes(row)
            well_casing_materials = (
                [] if isna(row.CasingDescription) else _extract_casing_materials(row)
            )

            # manually add the well rather than add_well from services/thing_helper.py
            # so that effective_start can be set on the location assocation
            data = CreateWell(
                location_id=location.id,
                nma_pk_welldata=row.WellID,
                name=row.PointID,
                first_visit_date=first_visit_date,
                hole_depth=row.HoleDepth,
                well_depth=row.WellDepth,
                well_construction_notes=row.ConstructionNotes,
                well_casing_diameter=row.CasingDiameter,
                well_casing_depth=row.CasingDepth,
                release_status="public" if row.PublicRelease else "private",
            )

            CreateWell.model_validate(data)
        except ValidationError as e:
            session.rollback()
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
            continue

        try:
            well_data = data.model_dump(
                exclude=[
                    "location_id",
                    "group_id",
                    "well_purposes",
                    "well_casing_materials",
                ]
            )
            well_data["thing_type"] = "water well"
            well = Thing(**well_data)
            session.add(well)

            if well_purposes:
                for wp in well_purposes:
                    wp_obj = WellPurpose(thing=well, purpose=wp)
                    session.add(wp_obj)

            if well_casing_materials:
                for wcm in well_casing_materials:
                    wcm_obj = WellCasingMaterial(thing=well, material=wcm)
                    session.add(wcm_obj)
        except Exception as e:
            session.rollback()
            logger.critical(f"Error creating well for {row.PointID}: {e}")
            continue

        assoc = LocationThingAssociation(effective_start=location.created_at)

        assoc.location = location
        assoc.thing = well
        session.add(assoc)

    session.commit()
    # try:
    #     session.commit()
    # except Exception as e:
    #     logger.critical(f"Error committing well {row.PointID}: {e}")
    #     session.rollback()
    #     continue


def transfer_wellscreens(session, limit=None):
    wdf = read_csv("WellScreens")
    wdf = replace_nans(wdf)

    wdf = filter_to_valid_point_ids(session, wdf)

    n = len(wdf)

    start_time = time.time()

    for i, row in enumerate(wdf.itertuples()):
        if limit and i >= limit:
            logger.warning("Reached limit of", limit, "rows. Stopping migration.")
            break

        # this is for testing only. not sure in practice we have to commit every 100 rows
        # should we commit every row? or every 1000? or every 10?
        if i and not i % 100:
            logger.info(
                f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
            )
            session.commit()

        sql = select(Thing).where(Thing.name == row.PointID)
        thing = session.execute(sql).unique().scalar_one_or_none()
        if not thing:
            logger.warning(
                f"Thing with PointID {row.PointID} not found. Skipping well screen."
            )
            continue

        well_screen_data = {
            "thing_id": thing.id,
            "screen_depth_top": row.ScreenTop,
            "screen_depth_bottom": row.ScreenBottom,
            # "screen_type": row.ScreenType,
            "screen_description": row.ScreenDescription,
            "release_status": "draft",
            "nma_pk_wellscreens": row.GlobalID,
        }
        try:
            # TODO: add validation logic here to ensure no overlapping screens for the same well
            CreateWellScreen.model_validate(well_screen_data)
            well_screen = WellScreen(**well_screen_data)
            session.add(well_screen)
        except ValidationError as e:
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
            continue

    session.commit()


def cleanup_locations(session):
    locations = session.query(Location).all()
    n = len(locations)
    lut = {}

    bucket = get_storage_bucket()
    log_filename = "transfer_data/location_cleanup.json"
    blob = bucket.blob(log_filename)
    if blob.exists():
        lut = json.loads(blob.download_as_string())

    updates = []
    for i, location in enumerate(locations):
        if i and not i % 100:
            logger.info(f"Processing row {i} of {n}. dumping lut to {log_filename}")
            blob.upload_from_string(json.dumps(lut))
            session.bulk_update_mappings(Location, updates)
            session.commit()
            updates = []

        y, x = location.latlon
        xykey = f"{y},{x}"
        if xykey in lut:
            state, county, quad_name = lut[xykey]
        else:
            state = location.state
            county = location.county
            quad_name = location.quad_name
            if not state:
                state = get_state_from_point(x, y)

            if not county:
                county = get_county_from_point(x, y)

            if not quad_name:
                quad_name = get_quad_name_from_point(x, y)

            lut[xykey] = [state, county, quad_name]

        updates.append(
            {
                "id": location.id,
                "state": state,
                "county": county,
                "quad_name": quad_name,
            }
        )

        logger.info(
            f"{i}/{n} lat: {y} lon: {x} state={state}, county={county}, quad"
            f"={quad_name}"
        )

    blob.upload_from_string(json.dumps(lut))
    if updates:
        session.bulk_update_mappings(Location, updates)
        session.commit()


# ============= EOF =============================================
