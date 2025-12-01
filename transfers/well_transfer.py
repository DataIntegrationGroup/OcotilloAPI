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
from datetime import datetime, UTC
import re
import pandas as pd
from pandas import isna
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.enums import (
    WellPurpose as WellPurposeEnum,
    CasingMaterial as WellCasingMaterialEnum,
)
from db import (
    LocationThingAssociation,
    Thing,
    WellScreen,
    Location,
    WellPurpose,
    WellCasingMaterial,
    StatusHistory,
    MonitoringFrequencyHistory,
    MeasuringPointHistory,
    DataProvenance,
)
from schemas.thing import CreateWell, CreateWellScreen
from services.gcs_helper import get_storage_bucket
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
from transfers.util import (
    make_location,
    make_location_data_provenance,
    filter_to_valid_point_ids,
    read_csv,
    logger,
    replace_nans,
    filter_by_welldata_datasource_and_project,
    lexicon_mapper,
    filter_non_transferred_wells,
    chunk_by_size,
)

ADDED = []

NMA_MONITORING_FREQUENCY = {
    "6": "Biannual",
    "A": "Annual",
    "B": "Bimonthly",
    "L": "Decadal",
    "M": "Monthly",
    "R": "Bimonthly reported",
    "N": "Biannual",
}


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


pattern = re.compile(
    r"\b(?P<term>jet|hand|submersible)\b|\b(?P<phrase>line[-\s]+shaft)\b", re.IGNORECASE
)


def first_matched_term(text: str):
    m = pattern.search(text)
    if not m:
        return None
    return m.group("term") or m.group("phrase")


PUMP_MAPPING = {"jet": "Jet", "hand": "Hand", "submersible": "Submersible"}


def _extract_well_pump_type(row) -> str | None:
    if isna(row.ConstructionNotes):
        return None
    construction_notes = row.ConstructionNotes.lower()
    return PUMP_MAPPING.get(first_matched_term(construction_notes), None)


def get_wells_to_transfer(
    sess: Session, flags: dict = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if flags is None:
        flags = {}

    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    ldf = read_csv("Location")
    ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1)
    wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
    wdf = wdf[wdf["SiteType"] == "GW"]
    wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

    input_df = wdf
    wdf = replace_nans(wdf)
    if flags.get("TRANSFER_ALL_WELLS", True):
        # todo: filter Locations by DataSource
        cleaned_df = filter_by_welldata_datasource_and_project(wdf)
    else:
        # get a subset of wells that have not been transferred yet
        # todo: this needs to be defined.
        #       for now, we are just filtering out wells that have not been transferred yet
        #       In the future we will be using criteria to determine which wells to transfer
        #       for example, wells in the "Water Level Network" project
        cleaned_df = wdf

    cleaned_df = filter_non_transferred_wells(sess, cleaned_df)

    return input_df, cleaned_df


def get_cached_elevations() -> dict:
    bucket = get_storage_bucket()
    log_filename = "transfer_data/cached_elevations.json"
    blob = bucket.blob(log_filename)
    if blob.exists():
        lut = json.loads(blob.download_as_string())
        return lut
    else:
        return {}


def dump_cached_elevations(lut: dict):
    bucket = get_storage_bucket()
    log_filename = "transfer_data/cached_elevations.json"
    blob = bucket.blob(log_filename)
    blob.upload_from_string(json.dumps(lut))


def transfer_wells(session: Session, flags: dict = None, limit: int = 0) -> None:
    input_df, cleaned_df = get_wells_to_transfer(session, flags)
    source_table = "WellData"
    wdf = cleaned_df
    n = len(wdf)

    step = 25
    start_time = time.time()
    errors = []
    added_locations = {}
    cached_elevations = get_cached_elevations()
    for i, row in enumerate(wdf.itertuples()):
        pointid = row.PointID
        if wdf[wdf["PointID"] == pointid].shape[0] > 1:
            logger.critical(
                f"transfer_wells. PointID {pointid} has duplicate records. Skipping."
            )
            errors.append(
                {
                    "pointid": pointid,
                    "error": "duplicate records",
                    "table": source_table,
                    "field": "PointID",
                }
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

        location = None
        try:
            location, elevation_method, location_notes = make_location(
                row, cached_elevations
            )
            session.add(location)

            added_locations[row.PointID] = elevation_method, location_notes
        except Exception as e:
            if location is not None:
                session.expunge(location)
            # these rollbacks are cause an issue because they are discarding good data
            # session.rollback()
            errors.append(
                {
                    "pointid": row.PointID,
                    "error": e,
                    "table": "Location",
                    "field": str(e),
                }
            )
            logger.critical(f"Error making location for {row.PointID}: {e}")
            continue

        try:
            first_visit_date = _get_first_visit_date(row)
            well_purposes = [] if isna(row.CurrentUse) else _extract_well_purposes(row)
            well_casing_materials = (
                [] if isna(row.CasingDescription) else _extract_casing_materials(row)
            )
            well_pump_type = _extract_well_pump_type(row)

            # manually add the well rather than add_well from services/thing_helper.py
            # so that effective_start can be set on the location assocation

            data = CreateWell(
                location_id=location.id,
                name=row.PointID,
                first_visit_date=first_visit_date,
                hole_depth=row.HoleDepth,
                well_depth=row.WellDepth,
                well_casing_diameter=(
                    row.CasingDiameter * 12 if row.CasingDiameter else None
                ),
                well_casing_depth=row.CasingDepth,
                release_status="public" if row.PublicRelease else "private",
                measuring_point_height=row.MPHeight,
                measuring_point_description=row.MeasuringPoint,
                well_completion_date=row.CompletionDate,
                well_driller_name=row.DrillerName,
                well_construction_method=(
                    lexicon_mapper.map_value(
                        f"LU_ConstructionMethod:{row.ConstructionMethod}"
                    )
                    if not isna(row.ConstructionMethod)
                    else None
                ),
                well_pump_type=well_pump_type,
                is_suitable_for_datalogger=(
                    bool(row.OpenWellLoggerOK)
                    if not isna(row.OpenWellLoggerOK)
                    else None
                ),
            )

            CreateWell.model_validate(data)
        except ValidationError as e:
            errors.append({"pointid": row.PointID, "error": e, "table": "WellData"})
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
            continue

        well = None
        try:
            well_data = data.model_dump(
                exclude=[
                    "location_id",
                    "group_id",
                    "well_purposes",
                    "well_casing_materials",
                    "measuring_point_height",
                    "measuring_point_description",
                    "well_completion_date_source",
                    "well_construction_method_source",
                    "notes",
                ]
            )
            well_data["thing_type"] = "water well"
            well_data["nma_pk_welldata"] = row.WellID

            well = Thing(**well_data)
            session.add(well)

            if well_purposes:
                for wp in well_purposes:
                    # TODO: add validation logic here
                    if wp in WellPurposeEnum:
                        wp_obj = WellPurpose(thing=well, purpose=wp)
                        session.add(wp_obj)
                    else:
                        logger.critical(f"{well.name}. Invalid well purpose: {wp}")

            if well_casing_materials:
                for wcm in well_casing_materials:
                    # TODO: add validation logic here
                    if wcm in WellCasingMaterialEnum:
                        wcm_obj = WellCasingMaterial(thing=well, material=wcm)
                        session.add(wcm_obj)
                    else:
                        logger.critical(
                            f"{well.name}. Invalid well casing material: {wcm}"
                        )
        except Exception as e:
            if well is not None:
                session.expunge(well)

            errors.append({"pointid": row.PointID, "error": e, "table": "WellData"})
            logger.critical(f"Error creating well for {row.PointID}: {e}")
            continue

        assoc = LocationThingAssociation(effective_start=location.created_at)

        assoc.location = location
        assoc.thing = well
        session.add(assoc)

    session.commit()

    # add things thate need well id
    for well in session.query(Thing).filter(Thing.thing_type == "water well").all():
        row = wdf[wdf["PointID"] == well.name].iloc[0]

        notes = []
        if row.Notes:
            notes.append({"content": row.Notes, "note_type": "Other"})
        if row.ConstructionNotes:
            notes.append(
                {"content": row.ConstructionNotes, "note_type": "Construction"}
            )
        if row.WaterNotes:
            notes.append({"content": row.WaterNotes, "note_type": "Water"})
        if notes:
            for note in notes:
                n = well.add_note(note["content"], note["note_type"])
                session.add(n)

        location = well.current_location
        elevation_method, location_notes = added_locations[row.PointID]
        data_provenances = make_location_data_provenance(
            row, location, elevation_method
        )

        for note_type, note_content in location_notes.items():
            if not isna(note_content):
                ln = location.add_note(note_content, note_type)
                session.add(ln)
                logger.info(
                    f"Added note of type {note_type} for current location of well {well.name}"
                )

        for dp in data_provenances:
            session.add(dp)

        if not isna(row.CompletionSource):
            dp = DataProvenance(
                target_id=well.id,
                target_table="thing",
                field_name="well_completion_date",
                origin_type=lexicon_mapper.map_value(
                    f"LU_Depth_CompletionSource:{row.CompletionSource}"
                ),
            )
            session.add(dp)

        if not isna(row.DataSource):
            dp = DataProvenance(
                target_id=well.id,
                target_table="thing",
                field_name="well_construction_method",
                origin_source=row.DataSource,
            )
            session.add(dp)

        if not isna(row.DepthSource):
            dp = DataProvenance(
                target_id=well.id,
                target_table="thing",
                field_name="well_depth",
                origin_type=lexicon_mapper.map_value(
                    f"LU_Depth_CompletionSource:{row.DepthSource}"
                ),
            )
            session.add(dp)

        """
        Developer's note

        It's not clear when the measuring point from NM_Aquifer was 
        determined, so I'm setting start_date to the day of the transfer
        """
        measuring_point_history = MeasuringPointHistory(
            thing_id=well.id,
            measuring_point_height=row.MPHeight,
            measuring_point_description=row.MeasuringPoint,
            start_date=datetime.now(tz=UTC),
            end_date=None,
        )
        session.add(measuring_point_history)

        """
        Developer's notes

        For all status_history records the start_date will be now since that
        isn't recorded in NM_Aquifer
        """
        # TODO: if row.MonitoringStatus == "Q" is it monitored or not? <-- AMMP review
        # TODO: if row.MonitoringStatus == "X" can that change? <-- AMMP review
        # TODO: have AMMP review and verify the various MonitoringStatus codes

        target_id = well.id
        target_table = "thing"
        if not isna(row.MonitoringStatus):
            if (
                "X" in row.MonitoringStatus
                or "I" in row.MonitoringStatus
                or "C" in row.MonitoringStatus
            ):
                status_value = "Not currently monitored"
            else:
                status_value = "Currently monitored"

            status_history = StatusHistory(
                status_type="Monitoring Status",
                status_value=status_value,
                reason=row.MonitorStatusReason,
                start_date=datetime.now(tz=UTC),
                target_id=target_id,
                target_table=target_table,
            )
            session.add(status_history)
            logger.info(
                f"  Added monitoring status for well {well.name}: {status_value}"
            )

            for code in NMA_MONITORING_FREQUENCY.keys():
                if code in row.MonitoringStatus:
                    monitoring_frequency = NMA_MONITORING_FREQUENCY[code]
                    monitoring_frequency_history = MonitoringFrequencyHistory(
                        thing_id=well.id,
                        monitoring_frequency=monitoring_frequency,
                        start_date=datetime.now(tz=UTC),
                        end_date=None,
                    )
                    session.add(monitoring_frequency_history)
                    logger.info(
                        f"  Adding '{monitoring_frequency}' monitoring frequency for well {well.name}"
                    )

        if not isna(row.Status):
            status_value = lexicon_mapper.map_value(f"LU_Status:{row.Status}")
            status_history = StatusHistory(
                status_type="Well Status",
                status_value=status_value,
                reason=row.StatusUserNotes,
                start_date=datetime.now(tz=UTC),
                target_id=target_id,
                target_table=target_table,
            )
            session.add(status_history)
            logger.info(f"  Added well status for well {well.name}: {status_value}")

    session.commit()

    dump_cached_elevations(cached_elevations)
    return input_df, cleaned_df, errors


def transfer_wellscreens(session, limit=None):

    input_df = read_csv("WellScreens")
    wdf = replace_nans(input_df)

    cleaned_df = filter_to_valid_point_ids(session, wdf)

    errors = []
    for ci, chunk in enumerate(chunk_by_size(cleaned_df, 1000)):
        things = (
            session.query(Thing).filter(Thing.name.in_(chunk.PointID.tolist())).all()
        )

        logger.info(f"Processing chunk {ci}, {len(chunk)} rows, {len(things)} things")
        for i, row in enumerate(chunk.itertuples()):
            thing = next((thing for thing in things if thing.name == row.PointID), None)
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
            except ValidationError as e:
                logger.critical(
                    f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
                )
                errors.append(
                    {"pointid": row.PointID, "error": e, "table": "WellScreens"}
                )
                continue

            well_screen = WellScreen(**well_screen_data)
            session.add(well_screen)

        session.commit()

    return input_df, cleaned_df, errors


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
