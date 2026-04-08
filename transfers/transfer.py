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
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy.dialects.postgresql import insert as pg_insert

from transfers.thing_transfer import (
    transfer_rock_sample_locations,
    transfer_springs,
    transfer_perennial_streams,
    transfer_ephemeral_streams,
    transfer_met_stations,
    transfer_diversion_of_surface_water,
    transfer_lake_pond_reservoir,
    transfer_soil_gas_sample_locations,
    transfer_other_site_types,
    transfer_outfall_wastewater_return_flow,
)

# Load .env file FIRST, before any database imports. Do not override
# environment variables already set by the runtime (e.g., Cloud Run jobs).
load_dotenv(override=False)

# In managed runtime environments, DB_DRIVER is occasionally omitted while
# CLOUD_SQL_* vars are present. Default to cloudsql in that case to avoid
# silently falling back to localhost/postgres settings.
if (
    not (os.getenv("DB_DRIVER") or "").strip()
    and (os.getenv("CLOUD_SQL_INSTANCE_NAME") or "").strip()
):
    os.environ["DB_DRIVER"] = "cloudsql"

from alembic import command
from alembic.config import Config

from db.engine import session_ctx
from db.initialization import recreate_public_schema, sync_search_vector_triggers
from services.env import get_bool_env
from transfers.aquifer_system_transfer import transfer_aquifer_systems
from transfers.geologic_formation_transfer import transfer_geologic_formations
from transfers.permissions_transfer import transfer_permissions
from transfers.stratigraphy_legacy import StratigraphyLegacyTransferer
from transfers.stratigraphy_transfer import transfer_stratigraphy

from transfers.waterlevels_transducer_transfer import (
    WaterLevelsContinuousPressureTransferer,
    WaterLevelsContinuousAcousticTransferer,
)

from transfers.metrics import Metrics
from transfers.profiling import (
    ProfileArtifact,
    upload_profile_artifacts,
)
from core.initializers import erase_and_rebuild_db, init_lexicon, init_parameter

from transfers.group_transfer import ProjectGroupTransferer
from transfers.link_ids_transfer import (
    LinkIdsWellDataTransferer,
    LinkIdsLocationDataTransferer,
)
from transfers.contact_transfer import ContactTransfer
from transfers.sensor_transfer import SensorTransferer
from transfers.waterlevels_transfer import WaterLevelTransferer
from transfers.well_transfer import (
    WellTransferer,
    WellScreenTransferer,
)
from transfers.well_transfer_util import cleanup_locations
from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer

from transfers.asset_transfer import AssetTransferer
from transfers.chemistry_sampleinfo import ChemistrySampleInfoTransferer
from transfers.field_parameters_transfer import FieldParametersTransferer
from transfers.hydraulicsdata import HydraulicsDataTransferer
from transfers.radionuclides import RadionuclidesTransferer
from transfers.major_chemistry import MajorChemistryTransferer
from transfers.ngwmn_views import (
    NGWMNLithologyTransferer,
    NGWMNWaterLevelsTransferer,
    NGWMNWellConstructionTransferer,
)
from transfers.associated_data import AssociatedDataTransferer
from transfers.soil_rock_results import SoilRockResultsTransferer
from transfers.surface_water_data import SurfaceWaterDataTransferer
from transfers.surface_water_photos import SurfaceWaterPhotosTransferer

from transfers.util import timeit
from transfers.waterlevelscontinuous_pressure_daily import (
    NMA_WaterLevelsContinuous_Pressure_DailyTransferer,
)
from transfers.weather_data import WeatherDataTransferer
from transfers.weather_photos import WeatherPhotosTransferer
from transfers.logger import logger, save_log_to_bucket
from transfers.transferer import Transferer
from transfers.util import read_csv
from db import GeologicFormation


@dataclass
class TransferOptions:
    transfer_screens: bool
    transfer_sensors: bool
    transfer_contacts: bool
    transfer_permissions: bool
    transfer_waterlevels: bool
    transfer_pressure: bool
    transfer_acoustic: bool
    transfer_link_ids: bool
    transfer_groups: bool
    transfer_assets: bool
    transfer_surface_water_photos: bool
    transfer_soil_rock_results: bool
    transfer_surface_water_data: bool
    transfer_hydraulics_data: bool
    transfer_chemistry_sampleinfo: bool
    transfer_field_parameters: bool
    transfer_major_chemistry: bool
    transfer_radionuclides: bool
    transfer_ngwmn_views: bool
    transfer_pressure_daily: bool
    transfer_weather_data: bool
    transfer_weather_photos: bool
    transfer_minor_trace_chemistry: bool
    transfer_nma_stratigraphy: bool
    transfer_associated_data: bool
    # Non-well location types
    transfer_springs: bool
    transfer_perennial_streams: bool
    transfer_ephemeral_streams: bool
    transfer_met_stations: bool
    transfer_rock_sample_locations: bool
    transfer_diversion_of_surface_water: bool
    transfer_lake_pond_reservoir: bool
    transfer_soil_gas_sample_locations: bool
    transfer_other_site_types: bool
    transfer_outfall_wastewater_return_flow: bool


def load_transfer_options() -> TransferOptions:
    """Read boolean toggles for each transfer from the environment."""

    return TransferOptions(
        transfer_screens=get_bool_env("TRANSFER_WELL_SCREENS", True),
        transfer_sensors=get_bool_env("TRANSFER_SENSORS", True),
        transfer_contacts=get_bool_env("TRANSFER_CONTACTS", True),
        transfer_permissions=get_bool_env("TRANSFER_PERMISSIONS", True),
        transfer_waterlevels=get_bool_env("TRANSFER_WATERLEVELS", True),
        transfer_pressure=get_bool_env("TRANSFER_WATERLEVELS_PRESSURE", True),
        transfer_acoustic=get_bool_env("TRANSFER_WATERLEVELS_ACOUSTIC", True),
        transfer_link_ids=get_bool_env("TRANSFER_LINK_IDS", True),
        transfer_groups=get_bool_env("TRANSFER_GROUPS", True),
        transfer_assets=get_bool_env("TRANSFER_ASSETS", True),
        transfer_surface_water_photos=get_bool_env(
            "TRANSFER_SURFACE_WATER_PHOTOS", True
        ),
        transfer_soil_rock_results=get_bool_env("TRANSFER_SOIL_ROCK_RESULTS", True),
        transfer_surface_water_data=get_bool_env("TRANSFER_SURFACE_WATER_DATA", True),
        transfer_hydraulics_data=get_bool_env("TRANSFER_HYDRAULICS_DATA", True),
        transfer_chemistry_sampleinfo=get_bool_env(
            "TRANSFER_CHEMISTRY_SAMPLEINFO", True
        ),
        transfer_field_parameters=get_bool_env("TRANSFER_FIELD_PARAMETERS", True),
        transfer_major_chemistry=get_bool_env("TRANSFER_MAJOR_CHEMISTRY", True),
        transfer_radionuclides=get_bool_env("TRANSFER_RADIONUCLIDES", True),
        transfer_ngwmn_views=get_bool_env("TRANSFER_NGWMN_VIEWS", True),
        transfer_pressure_daily=get_bool_env(
            "TRANSFER_WATERLEVELS_PRESSURE_DAILY", True
        ),
        transfer_weather_data=get_bool_env("TRANSFER_WEATHER_DATA", True),
        transfer_weather_photos=get_bool_env("TRANSFER_WEATHER_PHOTOS", True),
        transfer_minor_trace_chemistry=get_bool_env(
            "TRANSFER_MINOR_TRACE_CHEMISTRY", True
        ),
        transfer_nma_stratigraphy=get_bool_env("TRANSFER_NMA_STRATIGRAPHY", True),
        transfer_associated_data=get_bool_env("TRANSFER_ASSOCIATED_DATA", True),
        # Non-well location types
        transfer_springs=get_bool_env("TRANSFER_SPRINGS", True),
        transfer_perennial_streams=get_bool_env("TRANSFER_PERENNIAL_STREAMS", True),
        transfer_ephemeral_streams=get_bool_env("TRANSFER_EPHEMERAL_STREAMS", True),
        transfer_met_stations=get_bool_env("TRANSFER_MET_STATIONS", True),
        transfer_rock_sample_locations=get_bool_env(
            "TRANSFER_ROCK_SAMPLE_LOCATIONS", True
        ),
        transfer_diversion_of_surface_water=get_bool_env(
            "TRANSFER_DIVERSION_OF_SURFACE_WATER", True
        ),
        transfer_lake_pond_reservoir=get_bool_env("TRANSFER_LAKE_POND_RESERVOIR", True),
        transfer_soil_gas_sample_locations=get_bool_env(
            "TRANSFER_SOIL_GAS_SAMPLE_LOCATIONS", True
        ),
        transfer_other_site_types=get_bool_env("TRANSFER_OTHER_SITE_TYPES", True),
        transfer_outfall_wastewater_return_flow=get_bool_env(
            "TRANSFER_OUTFALL_WASTEWATER_RETURN_FLOW", True
        ),
    )


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


@contextmanager
def transfer_context(name: str, *, pad: int = 10):
    """Context manager to log start/end markers for a transfer block."""

    message(f"TRANSFERRING {name}", pad=pad)
    try:
        yield
    finally:
        logger.info("Finished %s", name)


def _get_test_pointids():
    return _normalize_test_pointids(os.getenv("TRANSFER_TEST_POINTIDS"))


def _normalize_test_pointids(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return Transferer._normalize_pointids(raw.split(","))


def _normalize_pointid_series(values: Iterable) -> set[str]:
    pointids: set[str] = set()
    for value in values:
        normalized = Transferer._normalize_pointid(value)
        if normalized is not None:
            pointids.add(normalized)
    return pointids


def _source_pointids(table_name: str, column: str = "PointID", **read_kw) -> set[str]:
    df = read_csv(table_name, **read_kw)
    if column not in df.columns:
        return set()
    return _normalize_pointid_series(df[column].tolist())


def _location_pointids_for_site_types(site_types: set[str]) -> set[str]:
    if not site_types:
        return set()
    df = read_csv("Location")
    if "SiteType" not in df.columns or "PointID" not in df.columns:
        return set()
    filtered = df[df["SiteType"].isin(site_types)]
    return _normalize_pointid_series(filtered["PointID"].tolist())


def _collect_available_scoped_pointids(transfer_options: TransferOptions) -> set[str]:
    available: set[str] = set()
    direct_sources: list[tuple[str, str, dict]] = []

    direct_sources.append(("WellData", "PointID", {"dtype": {"OSEWelltagID": str}}))

    if transfer_options.transfer_waterlevels:
        direct_sources.append(("WaterLevels", "PointID", {}))
    if transfer_options.transfer_pressure:
        direct_sources.append(
            (
                "WaterLevelsContinuous_Pressure",
                "PointID",
                {"parse_dates": ["DateMeasured"]},
            )
        )
    if transfer_options.transfer_acoustic:
        direct_sources.append(
            (
                "WaterLevelsContinuous_Acoustic",
                "PointID",
                {"parse_dates": ["DateMeasured"]},
            )
        )
    if transfer_options.transfer_pressure_daily:
        direct_sources.append(
            (
                "WaterLevelsContinuous_Pressure_Daily",
                "PointID",
                {"parse_dates": ["DateMeasured", "Created", "Updated"]},
            )
        )
    if transfer_options.transfer_assets:
        direct_sources.append(("WellPhotos", "PointID", {}))
    if transfer_options.transfer_sensors:
        direct_sources.append(("Equipment", "PointID", {}))
    if transfer_options.transfer_associated_data:
        direct_sources.append(("AssociatedData", "PointID", {}))
    if transfer_options.transfer_hydraulics_data:
        direct_sources.append(("HydraulicsData", "PointID", {}))
    if transfer_options.transfer_surface_water_data:
        direct_sources.append(
            ("SurfaceWaterData", "PointID", {"parse_dates": ["DateMeasured"]})
        )
    if transfer_options.transfer_surface_water_photos:
        direct_sources.append(("SurfaceWaterPhotos", "PointID", {}))
    if transfer_options.transfer_weather_data:
        direct_sources.append(("WeatherData", "PointID", {}))
    if transfer_options.transfer_weather_photos:
        direct_sources.append(("WeatherPhotos", "PointID", {}))
    if transfer_options.transfer_ngwmn_views:
        direct_sources.extend(
            [
                ("view_NGWMN_WellConstruction", "PointID", {}),
                (
                    "view_NGWMN_WaterLevels",
                    "PointID",
                    {"parse_dates": ["DateMeasured"]},
                ),
                ("view_NGWMN_Lithology", "PointID", {}),
            ]
        )
    if transfer_options.transfer_nma_stratigraphy:
        direct_sources.append(("Stratigraphy", "PointID", {}))
    if transfer_options.transfer_soil_rock_results:
        direct_sources.append(("Soil_Rock_Results", "Point_ID", {}))

    for table_name, column, read_kw in direct_sources:
        available.update(_source_pointids(table_name, column=column, **read_kw))

    location_site_types: set[str] = set()
    if any(
        (
            transfer_options.transfer_springs,
            transfer_options.transfer_perennial_streams,
            transfer_options.transfer_ephemeral_streams,
            transfer_options.transfer_met_stations,
            transfer_options.transfer_rock_sample_locations,
            transfer_options.transfer_diversion_of_surface_water,
            transfer_options.transfer_lake_pond_reservoir,
            transfer_options.transfer_soil_gas_sample_locations,
            transfer_options.transfer_other_site_types,
            transfer_options.transfer_outfall_wastewater_return_flow,
            transfer_options.transfer_weather_data,
            transfer_options.transfer_weather_photos,
            transfer_options.transfer_surface_water_data,
            transfer_options.transfer_surface_water_photos,
            transfer_options.transfer_soil_rock_results,
        )
    ):
        site_types_by_option = {
            "transfer_springs": "SP",
            "transfer_perennial_streams": "PS",
            "transfer_ephemeral_streams": "ES",
            "transfer_met_stations": "M",
            "transfer_rock_sample_locations": "R",
            "transfer_diversion_of_surface_water": "D",
            "transfer_lake_pond_reservoir": "L",
            "transfer_soil_gas_sample_locations": "S",
            "transfer_other_site_types": "OT",
            "transfer_outfall_wastewater_return_flow": "O",
        }
        for option_name, site_type in site_types_by_option.items():
            if getattr(transfer_options, option_name):
                location_site_types.add(site_type)
        if any(
            (
                transfer_options.transfer_weather_data,
                transfer_options.transfer_weather_photos,
            )
        ):
            location_site_types.add("M")
        if any(
            (
                transfer_options.transfer_surface_water_data,
                transfer_options.transfer_surface_water_photos,
            )
        ):
            location_site_types.update({"SP", "PS", "ES", "D", "L", "O"})
        if transfer_options.transfer_soil_rock_results:
            location_site_types.add("R")

    available.update(_location_pointids_for_site_types(location_site_types))
    return available


def _validate_scoped_pointids_or_raise(
    pointids: list[str], transfer_options: TransferOptions
) -> None:
    available_pointids = _collect_available_scoped_pointids(transfer_options)
    missing = sorted(set(pointids) - available_pointids)
    if missing:
        raise RuntimeError(
            "Scoped transfer preflight failed: requested PointIDs not found in "
            f"applicable source data: {missing}"
        )


def _seed_scoped_geologic_formations(
    pointids: list[str], transfer_options: TransferOptions
) -> None:
    required_codes: set[str] = set()
    pointid_set = set(pointids)

    well_df = read_csv("WellData", dtype={"OSEWelltagID": str})
    if "PointID" in well_df.columns and "FormationZone" in well_df.columns:
        filtered = well_df[
            well_df["PointID"].map(Transferer._normalize_pointid).isin(pointid_set)
        ]
        required_codes.update(
            _normalize_pointid_series(filtered["FormationZone"].tolist())
        )

    if transfer_options.transfer_nma_stratigraphy:
        strat_df = read_csv("Stratigraphy")
        if "PointID" in strat_df.columns and "UnitIdentifier" in strat_df.columns:
            filtered = strat_df[
                strat_df["PointID"].map(Transferer._normalize_pointid).isin(pointid_set)
            ]
            required_codes.update(
                _normalize_pointid_series(filtered["UnitIdentifier"].tolist())
            )

    if not required_codes:
        logger.info("Scoped run has no geologic formations to seed")
        return

    rows = [
        {"formation_code": code, "description": None, "lithology": None}
        for code in sorted(required_codes)
    ]
    with session_ctx() as session:
        stmt = (
            pg_insert(GeologicFormation)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["formation_code"])
        )
        session.execute(stmt)
        session.commit()
    logger.info("Seeded scoped geologic formations: %s", sorted(required_codes))


def _execute_transfer(klass, flags: dict = None, pointids: list[str] | None = None):
    """Execute a single transfer class. Thread-safe since each creates its own session."""
    transferer = klass(flags=flags, pointids=pointids)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


def _execute_transfer_with_timing(
    name: str, klass, flags: dict = None, pointids: list[str] | None = None
):
    """Execute transfer and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    effective_flags = dict(flags or {})
    yield_transfer_limit = effective_flags.get("LIMIT", 0)
    if yield_transfer_limit:
        effective_flags["LIMIT"] = max(1, yield_transfer_limit // 10)
    result = _execute_transfer(klass, effective_flags, pointids)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _execute_session_transfer_with_timing(
    name: str,
    transfer_func,
    limit: int,
    pointids: list[str] | None = None,
):
    """Execute a session-based transfer function and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    with session_ctx() as session:
        effective_limit = max(1, limit // 10) if limit else 0
        result = transfer_func(session, limit=effective_limit, pointids=pointids)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _execute_permissions_with_timing(name: str, pointids: list[str] | None = None):
    """Execute permissions transfer and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    with session_ctx() as session:
        transfer_permissions(session, pointids=pointids)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, None, elapsed


def _execute_foundational_transfer_with_timing(name: str, transfer_func, limit: int):
    """Execute a foundational transfer (aquifer systems, formations) with its own session."""
    start = time.time()
    logger.info(f"Starting parallel foundational transfer: {name}")
    with session_ctx() as session:
        result = transfer_func(session, limit=limit)
    elapsed = time.time() - start
    logger.info(f"Completed parallel foundational transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _alembic_config() -> Config:
    root = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(root, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "alembic"))
    return cfg


def _drop_and_rebuild_db() -> None:
    logger.info("Dropping schema public")
    with session_ctx() as session:
        recreate_public_schema(session)
    logger.info("Running Alembic migrations")

    try:
        command.upgrade(_alembic_config(), "head")
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise
        logger.info(
            "Alembic upgrade returned SystemExit(%s); continuing transfer", exc.code
        )
    logger.info("Alembic migrations complete")
    logger.info("Synchronizing search vector triggers")
    with session_ctx() as session:
        sync_search_vector_triggers(session)
    logger.info("Initializing lexicon data")
    init_lexicon()
    logger.info("Initializing parameter data")
    init_parameter()
    logger.info("Schema rebuild complete")


@timeit
def transfer_all(metrics: Metrics) -> list[ProfileArtifact]:
    message("STARTING TRANSFER", new_line_at_top=False)
    if get_bool_env("DROP_AND_REBUILD_DB", False):
        logger.info("Dropping schema and rebuilding database from migrations")
        _drop_and_rebuild_db()
    elif get_bool_env("ERASE_AND_REBUILD", False):
        logger.info("Erase and rebuilding database")
        erase_and_rebuild_db()

    # Get transfer flags
    message("TRANSFER OPTIONS")
    transfer_options = load_transfer_options()
    logger.info(
        "Transfer options: %s",
        {
            field: getattr(transfer_options, field)
            for field in transfer_options.__dataclass_fields__
        },
    )
    limit = int(os.getenv("TRANSFER_LIMIT", 1000))
    flags = {"TRANSFER_ALL_WELLS": True, "LIMIT": limit}
    message("TRANSFER_FLAGS")
    logger.info(flags)
    scoped_pointids = _get_test_pointids()
    if scoped_pointids:
        message("SCOPED TRANSFER MODE")
        logger.info("Scoped transfer mode active for PointIDs: %s", scoped_pointids)
        _validate_scoped_pointids_or_raise(scoped_pointids, transfer_options)
        logger.info("Preflight validation passed for requested PointIDs")

    profile_artifacts: list[ProfileArtifact] = []
    continuous_water_levels_only = get_bool_env("CONTINUOUS_WATER_LEVELS", False)

    # =========================================================================
    # PHASE 1: Foundation (Parallel - these are independent of each other)
    # =========================================================================
    if continuous_water_levels_only:
        logger.info("CONTINUOUS_WATER_LEVELS set; running only continuous transfers")
        _run_continuous_water_level_transfers(metrics, flags)
        return profile_artifacts
    else:
        message("PHASE 1: FOUNDATIONAL TRANSFERS (PARALLEL)")
        foundational_tasks = []
        if scoped_pointids:
            _seed_scoped_geologic_formations(scoped_pointids, transfer_options)
        else:
            foundational_tasks = [
                ("AquiferSystems", transfer_aquifer_systems),
                ("GeologicFormations", transfer_geologic_formations),
            ]

        if foundational_tasks:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        _execute_foundational_transfer_with_timing, name, func, limit
                    ): name
                    for name, func in foundational_tasks
                }

                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        result_name, result, elapsed = future.result()
                        logger.info(
                            f"Foundational transfer {result_name} completed in {elapsed:.2f}s"
                        )
                    except Exception as e:
                        logger.critical(f"Foundational transfer {name} failed: {e}")
                        raise  # Fail fast - foundational transfers must succeed
        elif scoped_pointids:
            logger.info("Skipping broad foundational lookup transfers in scoped mode")

        message("TRANSFERRING WELLS")
        use_parallel_wells = get_bool_env("TRANSFER_PARALLEL_WELLS", True)
        if use_parallel_wells:
            logger.info("Using PARALLEL wells transfer")
            transferer = WellTransferer(flags=flags, pointids=scoped_pointids)
            transferer.transfer_parallel()
            results = (transferer.input_df, transferer.cleaned_df, transferer.errors)
        else:
            results = _execute_transfer(
                WellTransferer, flags=flags, pointids=scoped_pointids
            )
        metrics.well_metrics(*results)

        # Get transfer flags
        transfer_options = load_transfer_options()

        # =========================================================================
        # PHASE 1.5: Non-well location types (parallel, after wells, before other transfers)
        # These create Things and Locations that chemistry/other transfers depend on.
        # =========================================================================
        non_well_tasks = []
        transfer_functions = {
            "transfer_springs": transfer_springs,
            "transfer_perennial_streams": transfer_perennial_streams,
            "transfer_ephemeral_streams": transfer_ephemeral_streams,
            "transfer_met_stations": transfer_met_stations,
            "transfer_rock_sample_locations": transfer_rock_sample_locations,
            "transfer_diversion_of_surface_water": transfer_diversion_of_surface_water,
            "transfer_lake_pond_reservoir": transfer_lake_pond_reservoir,
            "transfer_soil_gas_sample_locations": transfer_soil_gas_sample_locations,
            "transfer_other_site_types": transfer_other_site_types,
            "transfer_outfall_wastewater_return_flow": (
                transfer_outfall_wastewater_return_flow
            ),
        }

        for attr, thing_type in (
            ("springs", "Springs"),
            ("perennial_streams", "PerennialStreams"),
            ("ephemeral_streams", "EphemeralStreams"),
            ("met_stations", "MetStations"),
            ("rock_sample_locations", "RockSampleLocations"),
            ("diversion_of_surface_water", "DiversionOfSurfaceWater"),
            ("lake_pond_reservoir", "LakePondReservoir"),
            ("soil_gas_sample_locations", "SoilGasSampleLocations"),
            ("other_site_types", "OtherSiteTypes"),
            ("outfall_wastewater_return_flow", "OutfallWastewaterReturnFlow"),
        ):
            attr_name = f"transfer_{attr}"
            if getattr(transfer_options, attr_name):
                transfer_func = transfer_functions[attr_name]
                non_well_tasks.append((thing_type, transfer_func))

        if non_well_tasks:
            message("PHASE 1.5: NON-WELL LOCATION TYPES (PARALLEL)")
            with ThreadPoolExecutor(max_workers=len(non_well_tasks)) as executor:
                futures = {
                    executor.submit(
                        _execute_session_transfer_with_timing,
                        name,
                        func,
                        limit,
                        scoped_pointids,
                    ): name
                    for name, func in non_well_tasks
                }

                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        result_name, result, elapsed = future.result()
                        logger.info(
                            f"Non-well transfer {result_name} completed in {elapsed:.2f}s"
                        )
                    except Exception as e:
                        logger.critical(f"Non-well transfer {name} failed: {e}")

        _transfer_parallel(
            metrics,
            flags,
            limit,
            transfer_options,
            scoped_pointids,
        )

    return profile_artifacts


def _run_continuous_water_level_transfers(metrics, flags):
    message("CONTINUOUS WATER LEVEL TRANSFERS")
    pointids = _get_test_pointids()

    # =========================================================================
    # PHASE 4: Parallel Group 2 (Continuous water levels - after sensors)
    # =========================================================================
    message("PARALLEL TRANSFER GROUP 2 (Continuous Water Levels)")

    parallel_tasks = [
        ("Pressure", WaterLevelsContinuousPressureTransferer),
        ("Acoustic", WaterLevelsContinuousAcousticTransferer),
    ]
    results_map = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        for name, klass in parallel_tasks:
            future = executor.submit(
                _execute_transfer_with_timing,
                name,
                klass,
                flags,
                pointids,
            )
            futures[future] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                result_name, result, elapsed = future.result()
                results_map[result_name] = result
                logger.info(f"Parallel task {result_name} completed in {elapsed:.2f}s")
            except Exception:
                import traceback

                logger.critical(
                    f"Parallel task {name} failed: {traceback.format_exc()}"
                )

    if "Pressure" in results_map and results_map["Pressure"]:
        metrics.pressure_metrics(*results_map["Pressure"])
    if "Acoustic" in results_map and results_map["Acoustic"]:
        metrics.acoustic_metrics(*results_map["Acoustic"])


def _transfer_parallel(
    metrics,
    flags,
    limit,
    transfer_options: TransferOptions,
    pointids: list[str] | None = None,
):
    """Execute transfers in parallel where possible."""
    message("PARALLEL TRANSFER GROUP 1")
    opts = transfer_options

    # =========================================================================
    # PHASE 2: Parallel Group 1 (Independent transfers after wells)
    # =========================================================================
    parallel_tasks_1 = []

    if opts.transfer_screens:
        parallel_tasks_1.append(("WellScreens", WellScreenTransferer))
    if opts.transfer_contacts:
        parallel_tasks_1.append(("Contacts", ContactTransfer))
    if opts.transfer_waterlevels:
        parallel_tasks_1.append(("WaterLevels", WaterLevelTransferer))
    if opts.transfer_link_ids:
        parallel_tasks_1.append(("LinkIdsWellData", LinkIdsWellDataTransferer))
        parallel_tasks_1.append(("LinkIdsLocation", LinkIdsLocationDataTransferer))
    if opts.transfer_groups:
        parallel_tasks_1.append(("Groups", ProjectGroupTransferer))
    if opts.transfer_surface_water_photos:
        parallel_tasks_1.append(("SurfaceWaterPhotos", SurfaceWaterPhotosTransferer))
    if opts.transfer_soil_rock_results:
        parallel_tasks_1.append(("SoilRockResults", SoilRockResultsTransferer))
    if opts.transfer_weather_photos:
        parallel_tasks_1.append(("WeatherPhotos", WeatherPhotosTransferer))
    if opts.transfer_assets:
        parallel_tasks_1.append(("Assets", AssetTransferer))
    if opts.transfer_associated_data:
        parallel_tasks_1.append(("AssociatedData", AssociatedDataTransferer))
    if opts.transfer_surface_water_data:
        parallel_tasks_1.append(("SurfaceWaterData", SurfaceWaterDataTransferer))
    if opts.transfer_hydraulics_data:
        parallel_tasks_1.append(("HydraulicsData", HydraulicsDataTransferer))
    if opts.transfer_chemistry_sampleinfo:
        parallel_tasks_1.append(("ChemistrySampleInfo", ChemistrySampleInfoTransferer))
    if opts.transfer_ngwmn_views:
        parallel_tasks_1.append(
            ("NGWMNWellConstruction", NGWMNWellConstructionTransferer)
        )
        parallel_tasks_1.append(("NGWMNWaterLevels", NGWMNWaterLevelsTransferer))
        parallel_tasks_1.append(("NGWMNLithology", NGWMNLithologyTransferer))
    if opts.transfer_pressure_daily:
        parallel_tasks_1.append(
            (
                "WaterLevelsPressureDaily",
                NMA_WaterLevelsContinuous_Pressure_DailyTransferer,
            )
        )
    if opts.transfer_weather_data:
        parallel_tasks_1.append(("WeatherData", WeatherDataTransferer))
    if opts.transfer_nma_stratigraphy:
        parallel_tasks_1.append(("StratigraphyLegacy", StratigraphyLegacyTransferer))

    # Track results for metrics
    results_map = {}

    # Execute parallel group 1
    with ThreadPoolExecutor(max_workers=min(8, len(parallel_tasks_1) + 2)) as executor:
        futures = {}

        # Submit class-based transfers
        for name, klass in parallel_tasks_1:
            future = executor.submit(
                _execute_transfer_with_timing,
                name,
                klass,
                flags,
                pointids,
            )
            futures[future] = name

        future = executor.submit(
            _execute_session_transfer_with_timing,
            "StratigraphyNew",
            transfer_stratigraphy,
            limit,
            pointids,
        )
        futures[future] = "StratigraphyNew"

        # Collect results
        for future in as_completed(futures):
            name = futures[future]
            try:
                result_name, result, elapsed = future.result()
                results_map[result_name] = result
                logger.info(f"Parallel task {result_name} completed in {elapsed:.2f}s")
            except Exception as e:
                logger.critical(f"Parallel task {name} failed: {e}")

    # Record metrics for parallel group 1
    if "WellScreens" in results_map and results_map["WellScreens"]:
        metrics.well_screen_metrics(*results_map["WellScreens"])
    if "Contacts" in results_map and results_map["Contacts"]:
        metrics.contact_metrics(*results_map["Contacts"])
    if "StratigraphyNew" in results_map and results_map["StratigraphyNew"]:
        metrics.stratigraphy_metrics(*results_map["StratigraphyNew"])
    if "StratigraphyLegacy" in results_map and results_map["StratigraphyLegacy"]:
        metrics.nma_stratigraphy_metrics(*results_map["StratigraphyLegacy"])
    if "AssociatedData" in results_map and results_map["AssociatedData"]:
        metrics.associated_data_metrics(*results_map["AssociatedData"])
    if "WaterLevels" in results_map and results_map["WaterLevels"]:
        metrics.water_level_metrics(*results_map["WaterLevels"])
    if "LinkIdsWellData" in results_map and results_map["LinkIdsWellData"]:
        metrics.welldata_link_ids_metrics(*results_map["LinkIdsWellData"])
    if "LinkIdsLocation" in results_map and results_map["LinkIdsLocation"]:
        metrics.location_link_ids_metrics(*results_map["LinkIdsLocation"])
    if "Groups" in results_map and results_map["Groups"]:
        metrics.group_metrics(*results_map["Groups"])
    if "SurfaceWaterPhotos" in results_map and results_map["SurfaceWaterPhotos"]:
        metrics.surface_water_photos_metrics(*results_map["SurfaceWaterPhotos"])
    if "SoilRockResults" in results_map and results_map["SoilRockResults"]:
        metrics.soil_rock_results_metrics(*results_map["SoilRockResults"])
    if "Assets" in results_map and results_map["Assets"]:
        metrics.asset_metrics(*results_map["Assets"])
    if "SurfaceWaterData" in results_map and results_map["SurfaceWaterData"]:
        metrics.surface_water_data_metrics(*results_map["SurfaceWaterData"])
    if "HydraulicsData" in results_map and results_map["HydraulicsData"]:
        metrics.hydraulics_data_metrics(*results_map["HydraulicsData"])
    if "ChemistrySampleInfo" in results_map and results_map["ChemistrySampleInfo"]:
        metrics.chemistry_sampleinfo_metrics(*results_map["ChemistrySampleInfo"])
    if "NGWMNWellConstruction" in results_map and results_map["NGWMNWellConstruction"]:
        metrics.ngwmn_well_construction_metrics(*results_map["NGWMNWellConstruction"])
    if "NGWMNWaterLevels" in results_map and results_map["NGWMNWaterLevels"]:
        metrics.ngwmn_water_levels_metrics(*results_map["NGWMNWaterLevels"])
    if "NGWMNLithology" in results_map and results_map["NGWMNLithology"]:
        metrics.ngwmn_lithology_metrics(*results_map["NGWMNLithology"])
    if (
        "WaterLevelsPressureDaily" in results_map
        and results_map["WaterLevelsPressureDaily"]
    ):
        metrics.waterlevels_pressure_daily_metrics(
            *results_map["WaterLevelsPressureDaily"]
        )
    if "WeatherData" in results_map and results_map["WeatherData"]:
        metrics.weather_data_metrics(*results_map["WeatherData"])
    if "WeatherPhotos" in results_map and results_map["WeatherPhotos"]:
        metrics.weather_photos_metrics(*results_map["WeatherPhotos"])

    if opts.transfer_permissions:
        # Permissions require contact associations; run after group 1 completes.
        try:
            result_name, result, elapsed = _execute_permissions_with_timing(
                "Permissions",
                pointids,
            )
            results_map[result_name] = result
            logger.info(f"Task {result_name} completed in {elapsed:.2f}s")
        except Exception as e:
            logger.critical(f"Task Permissions failed: {e}")

    if opts.transfer_major_chemistry:
        message("TRANSFERRING MAJOR CHEMISTRY")
        results = _execute_transfer(
            MajorChemistryTransferer, flags=flags, pointids=pointids
        )
        metrics.major_chemistry_metrics(*results)

    if opts.transfer_radionuclides:
        message("TRANSFERRING RADIONUCLIDES")
        results = _execute_transfer(
            RadionuclidesTransferer, flags=flags, pointids=pointids
        )
        metrics.radionuclides_metrics(*results)

    if opts.transfer_minor_trace_chemistry:
        message("TRANSFERRING MINOR TRACE CHEMISTRY")
        results = _execute_transfer(
            MinorTraceChemistryTransferer, flags=flags, pointids=pointids
        )
        metrics.minor_trace_chemistry_metrics(*results)

    if opts.transfer_field_parameters:
        message("TRANSFERRING FIELD PARAMETERS")
        results = _execute_transfer(
            FieldParametersTransferer, flags=flags, pointids=pointids
        )
        metrics.field_parameters_metrics(*results)

    # =========================================================================
    # PHASE 3: Sensors (Sequential - required before continuous water levels)
    # =========================================================================
    if opts.transfer_sensors:
        message("TRANSFERRING SENSORS")
        results = _execute_transfer(SensorTransferer, flags=flags, pointids=pointids)
        metrics.sensor_metrics(*results)

    # # =========================================================================
    # # PHASE 4: Parallel Group 2 (Continuous water levels - after sensors)
    # # =========================================================================
    # Continuous water levels handled separately in _run_continuous_water_level_transfers()
    # the transfer process is bisected because the continuous water levels process is
    # very time consuming and we want to run it alone in its own phase.

    # =========================================================================
    # PHASE 5: Cleanup locations. populate state, county, quadname
    # =========================================================================
    if get_bool_env("CLEANUP_LOCATIONS", True):
        message("CLEANING UP LOCATIONS")
        with session_ctx() as session:
            cleanup_locations(session, pointids=pointids)


def main():
    message("START--------------------------------------")

    db_driver = (os.getenv("DB_DRIVER") or "").strip().lower()
    if db_driver == "cloudsql":
        db_name = os.getenv("CLOUD_SQL_DATABASE", "")
        instance_name = os.getenv("CLOUD_SQL_INSTANCE_NAME", "")
        iam_auth = os.getenv("CLOUD_SQL_IAM_AUTH", "")
        message(
            "Database Configuration: "
            f"driver=cloudsql instance={instance_name} db={db_name} iam_auth={iam_auth}"
        )
    else:
        # Display database configuration for verification
        db_name = os.getenv("POSTGRES_DB", "postgres")
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        message(f"Database Configuration: {db_host}:{db_port}/{db_name}")

        # Double-check we're using the development database
        if db_name != "ocotilloapi_dev":
            message(f"WARNING: Using database '{db_name}' instead of 'ocotilloapi_dev'")
            if db_name in ("ocotilloapi_test", "nmsamplelocations_test"):
                raise ValueError(
                    "ERROR: Cannot run transfer on test database! "
                    "Set POSTGRES_DB=ocotilloapi_dev in .env file"
                )

    metrics = Metrics()

    profile_artifacts = transfer_all(metrics)

    metrics.close()
    if get_bool_env("SAVE_TO_BUCKET", False):
        metrics.save_to_storage_bucket()
        save_log_to_bucket()
        upload_profile_artifacts(profile_artifacts)
    message("END--------------------------------------")


if __name__ == "__main__":
    main()
# ============= EOF =============================================
