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
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from zoneinfo import ZoneInfo

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
from db.engine import session_ctx
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

    def _extract_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f").date()

    if row.DateCreated and row.SiteDate:
        date_created = _extract_date(row.DateCreated)
        site_date = _extract_date(row.SiteDate)

        if date_created < site_date:
            first_visit_date = date_created
        else:
            first_visit_date = site_date
    elif row.DateCreated and not row.SiteDate:
        first_visit_date = _extract_date(row.DateCreated)
    elif not row.DateCreated and row.SiteDate:
        first_visit_date = _extract_date(row.SiteDate)

    return first_visit_date


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
        self._aquifers = None
        self._measuring_point_estimator = MeasuringPointEstimator()

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

        cleaned_df = get_transferable_wells(wdf, self.pointids)
        cleaned_df = filter_non_transferred_wells(cleaned_df)

        dupes = cleaned_df["PointID"].duplicated(keep=False)
        if dupes.any():
            dup_ids = set(cleaned_df.loc[dupes, "PointID"])
            logger.critical(f"{len(dup_ids)} PointIDs have duplicates; will skip.")
            logger.critical(f"Duplicate PointIDs: {dup_ids}")
            cleaned_df = cleaned_df[~cleaned_df["PointID"].isin(dup_ids)]

        cleaned_df = cleaned_df.sort_values(by=["PointID"])
        if self.pointids:
            cleaned_df = cleaned_df[cleaned_df["PointID"].isin(self.pointids)]
        return input_df, cleaned_df

    def _step(self, session: Session, df: pd.DataFrame, i: int, row: pd.Series):

        try:
            first_visit_date = _get_first_visit_date(row)
            well_purposes = (
                [] if isna(row.CurrentUse) else self._extract_well_purposes(row)
            )
            well_casing_materials = (
                [] if isna(row.CasingDescription) else _extract_casing_materials(row)
            )
            well_pump_type = _extract_well_pump_type(row)

            wcm = None
            if notna(row.ConstructionMethod):
                wcm = self._get_lexicon_value(
                    row, f"LU_ConstructionMethod:{row.ConstructionMethod}", "Unknown"
                )

            is_suitable_for_datalogger = False
            if notna(row.OpenWellLoggerOK):
                is_suitable_for_datalogger = bool(row.OpenWellLoggerOK)

            mpheight = row.MPHeight
            mpheight_description = row.MeasuringPoint
            if mpheight is None:
                mphs = self._measuring_point_estimator.estimate_measuring_point_height(
                    row
                )
                if mphs:
                    try:
                        mpheight = mphs[0][0]
                        mpheight_description = mphs[1][0]
                    except IndexError:
                        if self.verbose:
                            logger.warning(
                                f"Measuring point height estimation failed for well {row.PointID}, {mphs}"
                            )

            data = CreateWell(
                location_id=0,
                name=row.PointID,
                first_visit_date=first_visit_date,
                hole_depth=row.HoleDepth,
                well_depth=row.WellDepth,
                well_casing_diameter=(
                    row.CasingDiameter * 12 if row.CasingDiameter else None
                ),
                well_casing_depth=row.CasingDepth,
                release_status="public" if row.PublicRelease else "private",
                measuring_point_height=mpheight,
                measuring_point_description=mpheight_description,
                notes=(
                    [{"content": row.Notes, "note_type": "General"}]
                    if row.Notes
                    else []
                ),
                well_completion_date=row.CompletionDate,
                well_driller_name=row.DrillerName,
                well_construction_method=wcm,
                well_pump_type=well_pump_type,
                is_suitable_for_datalogger=is_suitable_for_datalogger,
            )

            CreateWell.model_validate(data)
        except ValidationError as e:
            self._capture_validation_error(row.PointID, e)
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

            self._capture_error(row.PointID, str(e), "UnknownField")

            logger.critical(f"Error creating well for {row.PointID}: {e}")
            return

        try:
            location, elevation_method, notes = make_location(
                row, self._cached_elevations
            )
            session.add(location)
            # session.flush()
            self._added_locations[row.PointID] = (elevation_method, notes)
        except Exception as e:
            import traceback

            traceback.print_exc()
            self._capture_error(row.PointID, str(e), str(e), "Location")
            logger.critical(f"Error making location for {row.PointID}: {e}")

            return

        assoc = LocationThingAssociation(
            effective_start=datetime.now(tz=ZoneInfo("UTC"))
        )

        assoc.location = location
        assoc.thing = well
        session.add(assoc)

        if isna(row.AquiferType):
            if self.verbose:
                logger.info(
                    f"No AquiferType for {well.name}. Skipping aquifer association."
                )
        else:
            if self.verbose:
                logger.info(f"Trying to associate aquifer for {well.name}")
            try:
                self._add_aquifers(session, row, well)
            except Exception as e:
                logger.critical(
                    f"Error creating aquifer association for {well.name}: {e}"
                )

    def _extract_well_purposes(self, row) -> list[str]:
        cu = row.CurrentUse

        if isna(cu):
            return []
        else:
            purposes = []
            for cui in cu:
                p = self._get_lexicon_value(row, f"LU_CurrentUse:{cui}")
                if p is not None:
                    purposes.append(p)
            return purposes

    def _add_formation_zone(self, row, well, formations):
        # --- Set Formation Completion (NOT depth-based stratigraphy) ---
        # This simply records which formation the well was completed in.
        # For detailed depth-interval stratigraphy, see stratigraphy_transfer.py

        formation_code = row.FormationZone
        if formation_code:
            formation_code = formation_code.strip()
            if formation_code in formations:
                # Formation exists: Set association
                well.formation_completion_code = formations[
                    formation_code
                ].formation_code
                if self.verbose:
                    logger.info(
                        f"Set completion formation for {well.name}: {formation_code}"
                    )
            else:
                # Formation does NOT exist: Do not create new formation. Flag and log for review
                self._capture_error(
                    row.PointID, f"Unknown formation: {formation_code}", "FormationZone"
                )

    def _get_lexicon_value(self, row, value, default=None):
        try:
            return lexicon_mapper.map_value(value)
        except KeyError:
            self._capture_error(
                row.PointID, f"Unknown lexicon value: {value}", "Unknown"
            )
            return default

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
            aquifer_name = self._get_lexicon_value(
                row, f"LU_AquiferType:{aquifer_codes[0]}"
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
                aquifer_name = self._get_lexicon_value(
                    row, f"LU_AquiferType:{aquifer_codes[0]}"
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

        if self._aquifers is None:
            self._aquifers = session.query(AquiferSystem).all()

        # Get or create the aquifer
        aquifer = self._get_or_create_aquifer_system(
            session, row, aquifer_name, primary_type
        )
        if aquifer:

            aquifer, created = aquifer
            if not aquifer:
                return

            if created:
                self._aquifers.append(aquifer)

            # Check if association already exists
            # existing_assoc = (
            #     session.query(ThingAquiferAssociation)
            #     .filter(
            #         ThingAquiferAssociation.thing_id == well.id,
            #         ThingAquiferAssociation.aquifer_system_id == aquifer.id,
            #     )
            #     .first()
            # )
            # if not existing_assoc:
            # Create the association
            if self.verbose:
                logger.info(f"Associating well {well.name} with aquifer {aquifer.name}")
            aquifer_assoc = ThingAquiferAssociation(thing=well, aquifer_system=aquifer)
            session.add(aquifer_assoc)
            # session.flush()

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

            if self.verbose:
                logger.info(
                    f"Associated well {well.name} with aquifer {aquifer.name} "
                    f"(types: {', '.join(aquifer_type_names)})"
                )
            # else:
            #     logger.info(
            #         f"Well {well.name} already associated with aquifer {aquifer.name}"
            #     )
        else:
            logger.info(f"Failed to create aquifer for well {well.name}")

    # Get or create aquifer system
    def _get_or_create_aquifer_system(
        self, session: Session, row, aquifer_name: str, primary_type: str
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
        # aquifer = (
        #     session.query(AquiferSystem).filter(AquiferSystem.name == aquifer_name).first()
        # )
        if aquifer_name is None:
            return None, False

        aquifer = next((a for a in self._aquifers if a.name == aquifer_name), None)
        if aquifer:
            return aquifer, False

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
            session.flush()  # Get the ID
            return aquifer, True
        except DatabaseError as e:
            session.rollback()
            self._capture_database_error(row.PointID, e)
            return None, False

    def _after_hook(self, session):
        dump_cached_elevations(self._cached_elevations)

        self._row_by_pointid = {
            pid: row
            for pid, row in self.cleaned_df.set_index("PointID", drop=False).iterrows()
        }

        formations = session.query(GeologicFormation).all()
        formations = {f.formation_code: f for f in formations}

        # add things thate need well id
        query = session.query(Thing).filter(Thing.thing_type == "water well")
        # query = (
        #     session.query(Thing)
        #     .options(
        #         selectinload(Thing.location_associations).selectinload(
        #             LocationThingAssociation.location
        #         )
        #     )
        #     .filter(Thing.thing_type == "water well")
        # )
        chunk_size = 500
        count = query.count()
        processed = 0
        chunk = []

        def _process_chunk(chunk_index: int, wells_chunk: list[Thing]):
            step_start_time = time.time()

            all_objects = []
            for well in wells_chunk:
                objs = self._after_hook_chunk(well, formations)
                if objs:
                    all_objects.extend(objs)

            save_time = time.time()
            try:
                session.bulk_save_objects(all_objects, return_defaults=False)
                session.commit()
            except DatabaseError as e:
                session.rollback()
                self._capture_database_error("MultiplePointIDs", e)
            finally:
                save_time = time.time() - save_time

            processed_count = chunk_index * chunk_size + len(wells_chunk)
            logger.info(
                f"After hook: {processed_count}/{count} took {time.time() - step_start_time:.2f}s, "
                f"n_objects={len(all_objects)}, save_time={save_time}"
            )
            return processed_count

        for well in query.all():
            chunk.append(well)
            if len(chunk) == chunk_size:
                processed = _process_chunk(processed // chunk_size, chunk)
                chunk = []

        if chunk:
            _process_chunk(processed // chunk_size, chunk)

    def _after_hook_chunk(self, well, formations):

        row = self._row_by_pointid.get(well.name)
        if row is None:
            return []

        objs = []
        self._add_formation_zone(row, well, formations)

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
            if notna(note_content):
                location_note = location.add_note(note_content, note_type)
                objs.append(location_note)
                if self.verbose:
                    logger.info(
                        f"Added note of type {note_type} for current location of well {well.name}"
                    )

        data_provenances = make_location_data_provenance(
            row, location, elevation_method
        )
        objs.extend(data_provenances)

        cs = (
            "CompletionSource",
            {
                "field_name": "well_completion_date",
                "origin_type": f"LU_Depth_CompletionSource:{row.CompletionSource}",
            },
        )
        ds = (
            "DataSource",
            {
                "field_name": "well_construction_method",
                "origin_source": row.DataSource,
            },
        )
        des = (
            "DepthSource",
            {
                "field_name": "well_depth",
                "origin_type": f"LU_Depth_CompletionSource:{row.DepthSource}",
            },
        )

        for row_field, kw in (cs, ds, des):
            if notna(row[row_field]):
                if "origin_type" in kw:
                    ot = self._get_lexicon_value(row, kw["origin_type"])
                    if ot is None:
                        continue

                    kw["origin_type"] = ot

                dp = DataProvenance(target_id=well.id, target_table="thing", **kw)
                objs.append(dp)

        start_time = time.time()
        mphs = self._measuring_point_estimator.estimate_measuring_point_height(row)
        if self.verbose:
            logger.info(
                f"Estimated measuring point heights for {well.name}: {time.time() - start_time:.2f}s"
            )
        for mph, mph_desc, start_date, end_date in zip(*mphs):
            measuring_point_history = MeasuringPointHistory(
                thing_id=well.id,
                measuring_point_height=mph,
                measuring_point_description=mph_desc,
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
            if self.verbose:
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
                    if self.verbose:
                        logger.info(
                            f"  Adding '{monitoring_frequency}' monitoring frequency for well {well.name}"
                        )

        if notna(row.Status):

            status_value = self._get_lexicon_value(row, f"LU_Status:{row.Status}")
            if status_value is not None:
                status_history = StatusHistory(
                    status_type="Well Status",
                    status_value=status_value,
                    reason=row.StatusUserNotes,
                    start_date=datetime.now(tz=UTC),
                    target_id=target_id,
                    target_table=target_table,
                )
                objs.append(status_history)
                if self.verbose:
                    logger.info(
                        f"  Added well status for well {well.name}: {status_value}"
                    )
        return objs

    def transfer_parallel(self, num_workers: int = None) -> None:
        """
        Transfer wells using parallel processing for improved performance.

        Each worker processes a batch of wells with its own database session.
        The after_hook runs sequentially after all workers complete.
        """
        if num_workers is None:
            num_workers = int(os.environ.get("TRANSFER_WORKERS", "4"))

        # Load dataframes
        self.input_df, self.cleaned_df = self._get_dfs()
        df = self.cleaned_df
        n = len(df)

        if n == 0:
            logger.info("No wells to transfer")
            return

        # Calculate batch size
        batch_size = max(100, n // num_workers)
        batches = [df.iloc[i : i + batch_size] for i in range(0, n, batch_size)]

        logger.info(
            f"Starting parallel transfer of {n} wells with {num_workers} workers, "
            f"{len(batches)} batches of ~{batch_size} wells each"
        )

        # Pre-load aquifers and formations to avoid race conditions
        with session_ctx() as session:
            self._aquifers = session.query(AquiferSystem).all()
            session.expunge_all()

        # Thread-safe collections for results
        all_errors = []
        errors_lock = threading.Lock()
        aquifers_lock = threading.Lock()

        def process_batch(batch_idx: int, batch_df: pd.DataFrame) -> dict:
            """Process a batch of wells in a separate thread with its own session."""
            batch_errors = []
            batch_start = time.time()

            try:
                with session_ctx() as session:
                    # Load aquifers and formations for this session
                    local_aquifers = session.query(AquiferSystem).all()
                    local_formations = {
                        f.formation_code: f
                        for f in session.query(GeologicFormation).all()
                    }

                    for i, row in enumerate(batch_df.itertuples()):
                        try:
                            # Process single well with all dependent objects
                            self._step_parallel_complete(
                                session,
                                batch_df,
                                i,
                                row,
                                local_aquifers,
                                local_formations,
                                batch_errors,
                                aquifers_lock,
                            )
                        except Exception as e:
                            batch_errors.append(
                                {
                                    "pointid": getattr(row, "PointID", "Unknown"),
                                    "error": str(e),
                                    "table": "WellData",
                                    "field": "Unknown",
                                }
                            )

                        # Commit periodically
                        if i > 0 and i % 100 == 0:
                            try:
                                session.commit()
                                session.expunge_all()
                                # Re-query after expunge
                                local_aquifers = session.query(AquiferSystem).all()
                                local_formations = {
                                    f.formation_code: f
                                    for f in session.query(GeologicFormation).all()
                                }
                            except Exception as e:
                                logger.critical(
                                    f"Batch {batch_idx}: Error committing: {e}"
                                )
                                session.rollback()

                    # Final commit for this batch
                    session.commit()

            except Exception as e:
                logger.critical(f"Batch {batch_idx} failed: {e}")
                batch_errors.append(
                    {
                        "pointid": "Batch",
                        "error": str(e),
                        "table": "WellData",
                        "field": "BatchProcessing",
                    }
                )

            elapsed = time.time() - batch_start
            logger.info(
                f"Batch {batch_idx}/{len(batches)} completed: {len(batch_df)} wells "
                f"in {elapsed:.2f}s ({len(batch_df)/elapsed:.1f} wells/sec)"
            )

            return {"errors": batch_errors}

        # Execute batches in parallel
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(process_batch, idx, batch): idx
                for idx, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    result = future.result()
                    with errors_lock:
                        all_errors.extend(result["errors"])
                except Exception as e:
                    logger.critical(f"Batch {batch_idx} raised exception: {e}")
                    with errors_lock:
                        all_errors.append(
                            {
                                "pointid": f"Batch-{batch_idx}",
                                "error": str(e),
                                "table": "WellData",
                                "field": "ThreadException",
                            }
                        )

        # Store merged results
        self.errors = all_errors

        logger.info(f"Parallel transfer complete: {n} wells, {len(all_errors)} errors")

        # Dump cached elevations (minimal after-processing)
        dump_cached_elevations(self._cached_elevations)

    def _step_parallel(
        self,
        session: Session,
        df: pd.DataFrame,
        i: int,
        row,
        local_aquifers: list,
        batch_locations: dict,
        batch_errors: list,
        aquifers_lock: threading.Lock,
    ):
        """
        Process a single well row in parallel mode.
        Similar to _step but uses thread-local state.
        """
        try:
            first_visit_date = _get_first_visit_date(row)
            well_purposes = (
                [] if isna(row.CurrentUse) else self._extract_well_purposes(row)
            )
            well_casing_materials = (
                [] if isna(row.CasingDescription) else _extract_casing_materials(row)
            )
            well_pump_type = _extract_well_pump_type(row)

            wcm = None
            if notna(row.ConstructionMethod):
                wcm = self._get_lexicon_value_safe(
                    row,
                    f"LU_ConstructionMethod:{row.ConstructionMethod}",
                    "Unknown",
                    batch_errors,
                )

            is_suitable_for_datalogger = False
            if notna(row.OpenWellLoggerOK):
                is_suitable_for_datalogger = bool(row.OpenWellLoggerOK)

            mpheight = row.MPHeight
            mpheight_description = row.MeasuringPoint
            if mpheight is None:
                mphs = self._measuring_point_estimator.estimate_measuring_point_height(
                    row
                )
                if mphs:
                    try:
                        mpheight = mphs[0][0]
                        mpheight_description = mphs[1][0]
                    except IndexError:
                        pass

            data = CreateWell(
                location_id=0,
                name=row.PointID,
                first_visit_date=first_visit_date,
                hole_depth=row.HoleDepth,
                well_depth=row.WellDepth,
                well_casing_diameter=(
                    row.CasingDiameter * 12 if row.CasingDiameter else None
                ),
                well_casing_depth=row.CasingDepth,
                release_status="public" if row.PublicRelease else "private",
                measuring_point_height=mpheight,
                measuring_point_description=mpheight_description,
                notes=(
                    [{"content": row.Notes, "note_type": "General"}]
                    if row.Notes
                    else []
                ),
                well_completion_date=row.CompletionDate,
                well_driller_name=row.DrillerName,
                well_construction_method=wcm,
                well_pump_type=well_pump_type,
                is_suitable_for_datalogger=is_suitable_for_datalogger,
            )

            CreateWell.model_validate(data)
        except ValidationError as e:
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": f"Validation Error: {e.errors()}",
                    "table": "WellData",
                    "field": "UnknownField",
                }
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
                    if wp in WellPurposeEnum:
                        wp_obj = WellPurpose(thing=well, purpose=wp)
                        session.add(wp_obj)

            if well_casing_materials:
                for wcm in well_casing_materials:
                    if wcm in WellCasingMaterialEnum:
                        wcm_obj = WellCasingMaterial(thing=well, material=wcm)
                        session.add(wcm_obj)
        except Exception as e:
            if well is not None:
                session.expunge(well)
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": str(e),
                    "table": "WellData",
                    "field": "UnknownField",
                }
            )
            return

        try:
            location, elevation_method, notes = make_location(
                row, self._cached_elevations
            )
            session.add(location)
            batch_locations[row.PointID] = (elevation_method, notes)
        except Exception as e:
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": str(e),
                    "table": "WellData",
                    "field": "Location",
                }
            )
            return

        assoc = LocationThingAssociation(
            effective_start=datetime.now(tz=ZoneInfo("UTC"))
        )
        assoc.location = location
        assoc.thing = well
        session.add(assoc)

        if not isna(row.AquiferType):
            try:
                self._add_aquifers_parallel(
                    session, row, well, local_aquifers, aquifers_lock
                )
            except Exception as e:
                logger.warning(f"Error adding aquifer for {well.name}: {e}")

    def _step_parallel_complete(
        self,
        session: Session,
        df: pd.DataFrame,
        i: int,
        row,
        local_aquifers: list,
        local_formations: dict,
        batch_errors: list,
        aquifers_lock: threading.Lock,
    ):
        """
        Process a single well with ALL dependent objects in one pass.
        Combines _step_parallel and _after_hook_chunk for maximum parallelization.
        """
        try:
            first_visit_date = _get_first_visit_date(row)
            well_purposes = (
                [] if isna(row.CurrentUse) else self._extract_well_purposes(row)
            )
            well_casing_materials = (
                [] if isna(row.CasingDescription) else _extract_casing_materials(row)
            )
            well_pump_type = _extract_well_pump_type(row)

            wcm = None
            if notna(row.ConstructionMethod):
                wcm = self._get_lexicon_value_safe(
                    row,
                    f"LU_ConstructionMethod:{row.ConstructionMethod}",
                    "Unknown",
                    batch_errors,
                )

            is_suitable_for_datalogger = False
            if notna(row.OpenWellLoggerOK):
                is_suitable_for_datalogger = bool(row.OpenWellLoggerOK)

            mpheight = row.MPHeight
            mpheight_description = row.MeasuringPoint
            if mpheight is None:
                mphs = self._measuring_point_estimator.estimate_measuring_point_height(
                    row
                )
                if mphs:
                    try:
                        mpheight = mphs[0][0]
                        mpheight_description = mphs[1][0]
                    except IndexError:
                        pass

            data = CreateWell(
                location_id=0,
                name=row.PointID,
                first_visit_date=first_visit_date,
                hole_depth=row.HoleDepth,
                well_depth=row.WellDepth,
                well_casing_diameter=(
                    row.CasingDiameter * 12 if row.CasingDiameter else None
                ),
                well_casing_depth=row.CasingDepth,
                release_status="public" if row.PublicRelease else "private",
                measuring_point_height=mpheight,
                measuring_point_description=mpheight_description,
                notes=(
                    [{"content": row.Notes, "note_type": "General"}]
                    if row.Notes
                    else []
                ),
                well_completion_date=row.CompletionDate,
                well_driller_name=row.DrillerName,
                well_construction_method=wcm,
                well_pump_type=well_pump_type,
                is_suitable_for_datalogger=is_suitable_for_datalogger,
            )

            CreateWell.model_validate(data)
        except ValidationError as e:
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": f"Validation Error: {e.errors()}",
                    "table": "WellData",
                    "field": "UnknownField",
                }
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
                    if wp in WellPurposeEnum:
                        wp_obj = WellPurpose(thing=well, purpose=wp)
                        session.add(wp_obj)

            if well_casing_materials:
                for wcm in well_casing_materials:
                    if wcm in WellCasingMaterialEnum:
                        wcm_obj = WellCasingMaterial(thing=well, material=wcm)
                        session.add(wcm_obj)
        except Exception as e:
            if well is not None:
                session.expunge(well)
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": str(e),
                    "table": "WellData",
                    "field": "UnknownField",
                }
            )
            return

        try:
            location, elevation_method, location_notes = make_location(
                row, self._cached_elevations
            )
            session.add(location)
        except Exception as e:
            batch_errors.append(
                {
                    "pointid": row.PointID,
                    "error": str(e),
                    "table": "WellData",
                    "field": "Location",
                }
            )
            return

        assoc = LocationThingAssociation(
            effective_start=datetime.now(tz=ZoneInfo("UTC"))
        )
        assoc.location = location
        assoc.thing = well
        session.add(assoc)

        # Flush to get IDs for dependent objects
        session.flush()

        # === Now add all dependent objects that need well.id and location.id ===

        # Aquifers
        if not isna(row.AquiferType):
            try:
                self._add_aquifers_parallel(
                    session, row, well, local_aquifers, aquifers_lock
                )
            except Exception as e:
                logger.warning(f"Error adding aquifer for {well.name}: {e}")

        # Formation zone
        formation_code = row.FormationZone if hasattr(row, "FormationZone") else None
        if formation_code:
            formation_code = formation_code.strip() if formation_code else None
            if formation_code:
                if formation_code in local_formations:
                    well.formation_completion_code = local_formations[
                        formation_code
                    ].formation_code
                else:
                    batch_errors.append(
                        {
                            "pointid": row.PointID,
                            "error": f"Unknown formation: {formation_code}",
                            "table": "WellData",
                            "field": "FormationZone",
                        }
                    )

        # Well notes
        if notna(row.Notes):
            note = well.add_note(row.Notes, "General")
            session.add(note)
        if row.ConstructionNotes:
            note = well.add_note(row.ConstructionNotes, "Construction")
            session.add(note)
        if row.WaterNotes:
            note = well.add_note(row.WaterNotes, "Water")
            session.add(note)

        # Location notes
        for note_type, note_content in location_notes.items():
            if notna(note_content):
                location_note = location.add_note(note_content, note_type)
                session.add(location_note)

        # Data provenances
        data_provenances = make_location_data_provenance(
            row, location, elevation_method
        )
        for dp in data_provenances:
            session.add(dp)

        # Well data provenances
        cs = (
            "CompletionSource",
            {
                "field_name": "well_completion_date",
                "origin_type": f"LU_Depth_CompletionSource:{row.CompletionSource}",
            },
        )
        ds = (
            "DataSource",
            {"field_name": "well_construction_method", "origin_source": row.DataSource},
        )
        des = (
            "DepthSource",
            {
                "field_name": "well_depth",
                "origin_type": f"LU_Depth_CompletionSource:{row.DepthSource}",
            },
        )

        for row_field, kw in (cs, ds, des):
            if notna(row[row_field]):
                if "origin_type" in kw:
                    try:
                        ot = lexicon_mapper.map_value(kw["origin_type"])
                        kw["origin_type"] = ot
                    except KeyError:
                        continue
                dp = DataProvenance(target_id=well.id, target_table="thing", **kw)
                session.add(dp)

        # Measuring point history
        mphs = self._measuring_point_estimator.estimate_measuring_point_height(row)
        for mph, mph_desc, start_date, end_date in zip(*mphs):
            measuring_point_history = MeasuringPointHistory(
                thing_id=well.id,
                measuring_point_height=mph,
                measuring_point_description=mph_desc,
                start_date=start_date,
                end_date=end_date,
            )
            session.add(measuring_point_history)

        # Status history
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
            session.add(status_history)

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

        if notna(row.Status):
            try:
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
            except KeyError:
                batch_errors.append(
                    {
                        "pointid": row.PointID,
                        "error": f"Unknown lexicon value: LU_Status:{row.Status}",
                        "table": "WellData",
                        "field": "Status",
                    }
                )

    def _get_lexicon_value_safe(self, row, value, default, errors_list):
        """Thread-safe version of _get_lexicon_value."""
        try:
            return lexicon_mapper.map_value(value)
        except KeyError:
            errors_list.append(
                {
                    "pointid": row.PointID,
                    "error": f"Unknown lexicon value: {value}",
                    "table": "WellData",
                    "field": "Unknown",
                }
            )
            return default

    def _add_aquifers_parallel(self, session, row, well, local_aquifers, aquifers_lock):
        """Thread-safe version of _add_aquifers."""
        aquifer_codes = _extract_aquifer_type_codes(row.AquiferType)
        if not aquifer_codes:
            return

        if isna(row.AqClass):
            try:
                aquifer_name = lexicon_mapper.map_value(
                    f"LU_AquiferType:{aquifer_codes[0]}"
                )
            except KeyError:
                return
        else:
            try:
                aquifer_name = lexicon_mapper.map_value(
                    f"LU_AquiferClass:{row.AqClass}"
                )
            except KeyError:
                try:
                    aquifer_name = lexicon_mapper.map_value(
                        f"LU_AquiferType:{aquifer_codes[0]}"
                    )
                except KeyError:
                    return

        if aquifer_name is None:
            return

        try:
            primary_type = lexicon_mapper.map_value(
                f"LU_AquiferType:{aquifer_codes[0]}"
            )
        except KeyError:
            primary_type = "Unknown"

        # Step 1: Check local cache under lock (fast check only)
        aquifer = None
        need_db_lookup = False

        with aquifers_lock:
            aquifer = next((a for a in local_aquifers if a.name == aquifer_name), None)
            if not aquifer:
                need_db_lookup = True

        # Step 2: Database operations OUTSIDE the lock to avoid deadlock
        if need_db_lookup:
            # Check if it exists in DB
            aquifer = (
                session.query(AquiferSystem)
                .filter(AquiferSystem.name == aquifer_name)
                .first()
            )

            if not aquifer:
                try:
                    aquifer = AquiferSystem(
                        name=aquifer_name,
                        primary_aquifer_type=primary_type,
                        geographic_scale=None,
                    )
                    session.add(aquifer)
                    session.flush()
                    logger.info(f"Created aquifer: {aquifer_name}")

                    # Update local cache under lock
                    with aquifers_lock:
                        # Check again to avoid duplicates
                        existing = next(
                            (a for a in local_aquifers if a.name == aquifer_name), None
                        )
                        if not existing:
                            local_aquifers.append(aquifer)
                except Exception as e:
                    # Race condition - another thread created it
                    session.rollback()
                    aquifer = (
                        session.query(AquiferSystem)
                        .filter(AquiferSystem.name == aquifer_name)
                        .first()
                    )

        if aquifer:
            aquifer_assoc = ThingAquiferAssociation(thing=well, aquifer_system=aquifer)
            session.add(aquifer_assoc)

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
                except KeyError:
                    pass


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
