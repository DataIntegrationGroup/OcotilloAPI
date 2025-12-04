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
import re
import time
from datetime import datetime, UTC

import pandas as pd
from pandas import isna, notna
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError
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
    AquiferSystem,
    AquiferType,
    GeologicFormation,
    ThingAquiferAssociation,
)
from schemas.thing import CreateWell, CreateWellScreen
from services.gcs_helper import get_storage_bucket
from services.util import (
    get_state_from_point,
    get_county_from_point,
    get_quad_name_from_point,
)
from transfers.transferer import ChunkTransferer, Transferer
from transfers.util import (
    make_location,
    make_location_data_provenance,
    filter_to_valid_point_ids,
    read_csv,
    logger,
    replace_nans,
    get_transferable_wells,
    lexicon_mapper,
    filter_non_transferred_wells,
    MeasuringPointEstimator,
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


PUMP_PATTERN = re.compile(
    r"\b(?P<term>jet|hand|submersible)\b|\b(?P<phrase>line[-\s]+shaft)\b", re.IGNORECASE
)


def first_matched_term(text: str):
    m = PUMP_PATTERN.search(text)
    if not m:
        return None
    return m.group("term") or m.group("phrase")


def _extract_well_pump_type(row) -> str | None:
    if isna(row.ConstructionNotes):
        return None
    construction_notes = row.ConstructionNotes.lower()
    pump = first_matched_term(construction_notes)
    if pump:
        return pump.capitalize()
    else:
        return None


# Parse aquifer codes
def _extract_aquifer_type_codes(aquifer_code: str) -> list[str]:
    """
    Parse aquifer type codes that may contain multiple values.

    Args:
        aquifer_code: Raw code from AquiferType field

    Returns:
        List of individual codes
    """
    if not aquifer_code:
        return []
    # clean the code
    code = aquifer_code.strip().upper()
    # split into individual characters. This handles cases like "FC" -> ["F", "C"]
    individual_codes = list(code)
    return individual_codes


# Get or create aquifer system
def get_or_create_aquifer_system(
    session: Session, aquifer_name: str, primary_type: str
) -> AquiferSystem | None:
    """
    Get existing aquifer or create new one if it doesn't exist.

    With the new AquiferType model, we create ONE aquifer record per named
    aquifer (e.g., one "Santa Fe Group"), not multiple variants.

    Args:
        session: Database session
        aquifer_name: Name of the aquifer (from AqClass or type name)
        primary_type: Primary aquifer type for the aquifer_type field
    """
    # Try to find existing aquifer by name
    aquifer = (
        session.query(AquiferSystem).filter(AquiferSystem.name == aquifer_name).first()
    )

    if aquifer:
        return aquifer

    # Create new aquifer
    try:
        logger.info(
            f"Creating new aquifer system: {aquifer_name} (primary type: {primary_type})"
        )

        aquifer = AquiferSystem(
            name=aquifer_name,
            primary_aquifer_type=primary_type,  # Primary type
            geographic_scale=None,  # Default
        )
        session.add(aquifer)
        session.commit()
        # session.flush()  # Get the ID
        # session.refresh(aquifer)
        return aquifer
    except DatabaseError as e:
        session.rollback()
        logger.critical(f"Error creating aquifer {aquifer_name}: {e}")
        return None


def get_or_create_geologic_formation(
    session: Session, formation_code: str
) -> GeologicFormation | None:
    """
    Get existing geologic formation or create new one if it doesn't exist.

    Args:
        session: Database session
        formation_code: The formation code from FormationZone field

    Returns:
        GeologicFormation object or None if creation fails
    """
    # Try to find existing formation
    formation = (
        session.query(GeologicFormation)
        .filter(GeologicFormation.formation_code == formation_code)
        .first()
    )

    if formation:
        return formation

    # If not found, create new formation
    try:
        logger.info(f"Creating new geologic formation: {formation_code}")
        formation = GeologicFormation(
            formation_code=formation_code,
            description=None,
            lithology=None,
        )
        session.add(formation)
        session.flush()
        return formation
    except Exception as e:
        logger.critical(f"Error creating formation {formation_code}: {e}")
        return None


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


class WellTransferer(Transferer):
    source_table = "WellData"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self._cached_elevations = get_cached_elevations()
        self._added_locations = {}

    def _get_dfs(self):
        wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
        ldf = read_csv("Location")
        ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1)
        wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
        wdf = wdf[wdf["SiteType"] == "GW"]
        wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]

        input_df = wdf
        wdf = replace_nans(wdf)

        # if flags.get("TRANSFER_ALL_WELLS", False):
        #     # todo: filter Locations by DataSource
        #     cleaned_df = filter_by_welldata_datasource_and_project(wdf)
        # else:
        #     # get a subset of wells that have not been transferred yet
        #     # todo: this needs to be defined.
        #     #       for now, we are just filtering out wells that have not been transferred yet
        #     #       In the future we will be using criteria to determine which wells to transfer
        #     #       for example, wells in the "Water Level Network" project
        #     cleaned_df = wdf

        cleaned_df = get_transferable_wells(wdf)
        cleaned_df = filter_non_transferred_wells(cleaned_df)

        return input_df, cleaned_df

    def _step(self, session: Session, df: pd.DataFrame, i: int, row: pd.Series):
        pointid = row.PointID
        if df[df["PointID"] == pointid].shape[0] > 1:
            logger.critical(
                f"transfer_wells. PointID {pointid} has duplicate records. Skipping."
            )
            self._capture_error(pointid, "duplicate records", "PointID")
            return

        location = None
        try:
            location, elevation_method, location_notes = make_location(
                row, self._cached_elevations
            )
            session.add(location)
            session.commit()
            self._added_locations[row.PointID] = elevation_method, location_notes
        except Exception as e:
            self._capture_error(row.PointID, str(e), str(e), "Location")
            logger.critical(f"Error making location for {row.PointID}: {e}")

            if location is not None:
                session.expunge(location)

            return

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
                notes=(
                    [{"content": row.Notes, "note_type": "Other"}] if row.Notes else []
                ),
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
            self._capture_error(row.PointID, str(e), "UnknownField")
            logger.critical(
                f"Validation error for row {i} with PointID {row.PointID}: {e.errors()}"
            )
            return

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
                ]
            )
            well_data["thing_type"] = "water well"
            well_data["nma_pk_welldata"] = row.WellID

            well_data.pop("notes")
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

            if location is not None:
                session.delete(location)

            self._capture_error(row.PointID, str(e), "UnknownField")

            logger.critical(f"Error creating well for {row.PointID}: {e}")
            return

        assoc = LocationThingAssociation(effective_start=location.created_at)

        assoc.location = location
        assoc.thing = well
        session.add(assoc)

        if isna(row.AquiferType):
            logger.info(
                f"No AquiferType for {well.name}. Skipping aquifer association."
            )
        else:
            try:
                self._add_aquifers(session, row, well)
            except Exception as e:
                logger.critical(
                    f"Error creating aquifer association for {well.name}: {e}"
                )

        if isna(row.FormationZone):
            logger.info(
                f"No FormationZone for {well.name}. Skipping formation association."
            )
        else:
            try:
                self._add_formation_zone(session, row, well)
            except Exception as e:
                logger.critical(
                    f"Error creating formation association for {well.name}: {e}"
                )

    def _add_formation_zone(self, session, row, well):
        # --- Set Formation Completion (NOT depth-based stratigraphy) ---
        # This simply records which formation the well was completed in.
        # For detailed depth-interval stratigraphy, see stratigraphy_transfer.py

        formation_code = row.FormationZone

        # Validate formation exists
        formation = (
            session.query(GeologicFormation)
            .filter(GeologicFormation.formation_code == formation_code)
            .first()
        )

        if formation:
            # Formation exists: Set association
            well.formation_completion_code = formation_code
            logger.info(f"Set completion formation for {well.name}: {formation_code}")
        else:
            # Formation does NOT exist: Do not create new formation. Flag and log for review
            logger.critical(
                f"MISSING FORMATION: Formation '{formation_code}' not found for well {well.name}. Flagged for review."
            )
            self._capture_error(
                row.PointID, f"Unknown formation: {formation_code}", "FormationZone"
            )

    def _add_aquifers(self, session, row, well):
        # Parse codes (handles multi-character codes like "FC")
        aquifer_codes = _extract_aquifer_type_codes(row.AquiferType)

        if not aquifer_codes:
            logger.warning(
                f"Well {row.PointID}: Empty aquifer codes after parsing '{row.AquiferType}'"
            )
            return

        # Map AqClass code to aquifer name using lexicon mapper
        if isna(row.AqClass):
            # No AqClass - use first code's mapped name as aquifer name
            aquifer_name = lexicon_mapper.map_value(
                f"LU_AquiferType:{aquifer_codes[0]}"
            )
        else:
            try:
                aquifer_name = lexicon_mapper.map_value(
                    f"LU_AquiferClass:{row.AqClass}"
                )
            except KeyError:
                logger.warning(
                    f"Unknown AqClass code '{row.AqClass}' for well {row.PointID}, using first type as name"
                )
                aquifer_name = lexicon_mapper.map_value(
                    f"LU_AquiferType:{aquifer_codes[0]}"
                )

        # Determine primary type
        # This assumes the first recorded type of a compound type is the primary type of the aquifer.
        # TODO: verify with AMMP
        try:
            primary_type = lexicon_mapper.map_value(
                f"LU_AquiferType:{aquifer_codes[0]}"
            )
        except KeyError:
            logger.warning(
                f"Unknown aquifer type code '{aquifer_codes[0]}' for well {row.PointID}."
                f"Setting primary_type to 'Unknown'"
            )
            primary_type = "Unknown"  # Creates aquifer with placeholder

        # Get or create the aquifer
        aquifer = get_or_create_aquifer_system(session, aquifer_name, primary_type)
        if aquifer:
            # Check if association already exists
            existing_assoc = (
                session.query(ThingAquiferAssociation)
                .filter(
                    ThingAquiferAssociation.thing_id == well.id,
                    ThingAquiferAssociation.aquifer_system_id == aquifer.id,
                )
                .first()
            )

            if not existing_assoc:
                # Create the association
                logger.info(f"Associating well {well.name} with aquifer {aquifer.name}")
                aquifer_assoc = ThingAquiferAssociation(
                    thing=well, aquifer_system=aquifer
                )
                session.add(aquifer_assoc)
                session.flush()

                # Create AquiferType records for EACH characteristic
                aquifer_type_names = []
                for aquifer_code in aquifer_codes:
                    try:
                        type_name = lexicon_mapper.map_value(
                            f"LU_AquiferType:{aquifer_code}"
                        )
                        aquifer_type = AquiferType(
                            thing_aquifer_association=aquifer_assoc,
                            aquifer_type=type_name,
                        )
                        session.add(aquifer_type)
                        aquifer_type_names.append(type_name)
                    except KeyError:
                        logger.critical(
                            f"Unknown aquifer code '{aquifer_code}' from AquiferType='{row.AquiferType}' "
                            f"for well {well.name}. Skipping this code."
                        )
                        self._capture_error(
                            row.PointID,
                            f"Unknown aquifer code: {aquifer_code}",
                            "AquiferType",
                        )

                logger.info(
                    f"Associated well {well.name} with aquifer {aquifer.name} "
                    f"(types: {', '.join(aquifer_type_names)})"
                )

    def _after_hook(self, session):
        dump_cached_elevations(self._cached_elevations)
        measuring_point_estimator = MeasuringPointEstimator()
        # add things thate need well id
        query = session.query(Thing).filter(Thing.thing_type == "water well")
        count = query.count()
        for i, well in enumerate(query.all()):
            objs = []
            step_start_time = time.time()
            row = self.cleaned_df[self.cleaned_df["PointID"] == well.name].iloc[0]
            if notna(row.Notes):
                note = well.add_note(row.Notes, "General")
                objs.append(note)
            if row.ConstructionNotes:
                note = well.add_note(row.ConstructionNotes, "Construction")
                objs.append(note)
            if row.WaterNotes:
                note = well.add_note(row.WaterNotes, "Water")
                objs.append(note)

            location = well.current_location
            elevation_method, location_notes = self._added_locations[row.PointID]
            for note_type, note_content in location_notes.items():
                if not isna(note_content):
                    location_note = location.add_note(note_content, note_type)
                    objs.append(location_note)
                    logger.info(
                        f"Added note of type {note_type} for current location of well {well.name}"
                    )
            data_provenances = make_location_data_provenance(
                row, location, elevation_method
            )
            objs.extend(data_provenances)

            for row_field, kw in (
                (
                    "CompletionSource",
                    dict(
                        field_name="well_completion_date",
                        origin_type=lexicon_mapper.map_value(
                            f"LU_Depth_CompletionSource:{row.CompletionSource}"
                        ),
                    ),
                ),
                (
                    "DataSource",
                    dict(
                        field_name="well_construction_method",
                        origin_source=row.DataSource,
                    ),
                ),
                (
                    "DepthSource",
                    dict(
                        field_name="well_depth",
                        origin_type=lexicon_mapper.map_value(
                            f"LU_Depth_CompletionSource:{row.DepthSource}"
                        ),
                    ),
                ),
            ):

                if notna(row[row_field]):
                    dp = DataProvenance(target_id=well.id, target_table="thing", **kw)
                    objs.append(dp)

            start_time = time.time()
            mphs = measuring_point_estimator.estimate_measuring_point_height(row)
            logger.info(
                f"Estimated measuring point heights for {well.name}: {time.time() - start_time:.2f}s"
            )
            for mph, mph_desc, start_date, end_date in mphs:
                measuring_point_history = MeasuringPointHistory(
                    thing_id=well.id,
                    measuring_point_height=mph,
                    measuring_point_description=mph_desc,
                    # start_date=datetime.now(tz=UTC),
                    start_date=start_date,
                    end_date=end_date,
                )
                objs.append(measuring_point_history)

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
            if notna(row.MonitoringStatus):
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
                objs.append(status_history)
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

                        objs.append(monitoring_frequency_history)
                        logger.info(
                            f"  Adding '{monitoring_frequency}' monitoring frequency for well {well.name}"
                        )

            if notna(row.Status):
                status_value = lexicon_mapper.map_value(f"LU_Status:{row.Status}")
                status_history = StatusHistory(
                    status_type="Well Status",
                    status_value=status_value,
                    reason=row.StatusUserNotes,
                    start_date=datetime.now(tz=UTC),
                    target_id=target_id,
                    target_table=target_table,
                )
                objs.append(status_history)
                logger.info(f"  Added well status for well {well.name}: {status_value}")
            try:
                session.bulk_save_objects(objs)
            except DatabaseError as e:
                session.rollback()
                error_dict = e.orig.args[0]
                self._capture_error(well.name, error_dict["D"], error_dict["t"])

            logger.info(
                f"After hook: {well.name} {i+1}/{count} took {time.time() - step_start_time:.2f}s"
            )


class WellChunkTransferer(ChunkTransferer):
    source_table: str = None
    source_dtypes: dict = None

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        if self.source_table is None:
            raise ValueError("source_table must be set")

    def _get_dfs(self):
        if self.source_table is None:
            raise ValueError("source_table must be set")

        input_df = read_csv(self.source_table, self.source_dtypes)
        wdf = replace_nans(input_df)
        cleaned_df = filter_to_valid_point_ids(wdf)
        return input_df, cleaned_df

    def _get_df_chunk(self, session, chunk):
        things = (
            session.query(Thing).filter(Thing.name.in_(chunk.PointID.tolist())).all()
        )
        return things

    def _get_db_item(self, dbchunk, row):
        return next((thing for thing in dbchunk if thing.name == row.PointID), None)

    def _missing_db_item_warning(self, row):
        logger.warning(f"Thing with PointID {row.PointID} not found in database.")


class WellScreenTransferer(WellChunkTransferer):
    source_table = "WellScreens"

    def _chunk_step(self, session, df, i, row, db_item):
        well_screen_data = {
            "thing_id": db_item.id,
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
            self._capture_error(row.PointID, str(e), "UnknownField")
            return

        well_screen = WellScreen(**well_screen_data)
        session.add(well_screen)


# def transfer_wells(flags: dict = None):
#     transferer = WellTransferer(flags=flags)
#     transferer.transfer()
#     return transferer.input_df, transferer.cleaned_df, transferer.errors
#
#
# def transfer_wellscreens(flags: dict = None):
#     transferer = WellScreenTransferer(flags=flags)
#     transferer.chunk_transfer()
#     return transferer.input_df, transferer.cleaned_df, transferer.errors


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
