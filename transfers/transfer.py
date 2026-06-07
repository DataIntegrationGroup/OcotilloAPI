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
"""DEPRECATED: legacy NM_Aquifer -> Ocotillo transfer orchestrator.

This module (the original AMPAPI / NM_Aquifer migration driver) is deprecated.
Do not add new migrations here. New migrations get their own standalone
orchestrator script; e.g. the NM_Wells geothermal migration lives in
``transfers/transfer_geothermal.py``.
"""
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass

from dotenv import load_dotenv

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
    pointids = None
    if os.getenv("TRANSFER_TEST_POINTIDS"):
        pointids = os.getenv("TRANSFER_TEST_POINTIDS").split(",")
    return pointids


def _execute_transfer(klass, flags: dict = None):
    """Execute a single transfer class. Thread-safe since each creates its own session."""
    transferer = klass(flags=flags, pointids=_get_test_pointids())
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


def _execute_transfer_with_timing(name: str, klass, flags: dict = None):
    """Execute transfer and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    effective_flags = dict(flags or {})
    yield_transfer_limit = effective_flags.get("LIMIT", 0)
    if yield_transfer_limit:
        effective_flags["LIMIT"] = max(1, yield_transfer_limit // 10)
    result = _execute_transfer(klass, effective_flags)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _execute_session_transfer_with_timing(name: str, transfer_func, limit: int):
    """Execute a session-based transfer function and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    with session_ctx() as session:
        effective_limit = max(1, limit // 10) if limit else 0
        result = transfer_func(session, limit=effective_limit)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _execute_permissions_with_timing(name: str):
    """Execute permissions transfer and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    with session_ctx() as session:
        transfer_permissions(session)
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
    warnings.warn(
        "transfers.transfer is deprecated; new migrations get their own "
        "orchestrator (e.g. transfers/transfer_geothermal.py).",
        DeprecationWarning,
        stacklevel=2,
    )
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
        foundational_tasks = [
            ("AquiferSystems", transfer_aquifer_systems),
            ("GeologicFormations", transfer_geologic_formations),
        ]

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

        message("TRANSFERRING WELLS")
        use_parallel_wells = get_bool_env("TRANSFER_PARALLEL_WELLS", True)
        if use_parallel_wells:
            logger.info("Using PARALLEL wells transfer")
            transferer = WellTransferer(flags=flags, pointids=_get_test_pointids())
            transferer.transfer_parallel()
            results = (transferer.input_df, transferer.cleaned_df, transferer.errors)
        else:
            results = _execute_transfer(WellTransferer, flags=flags)
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
                        _execute_session_transfer_with_timing, name, func, limit
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
        )

    return profile_artifacts


def _run_continuous_water_level_transfers(metrics, flags):
    message("CONTINUOUS WATER LEVEL TRANSFERS")

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
            future = executor.submit(_execute_transfer_with_timing, name, klass, flags)
            futures[future] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                result_name, result, elapsed = future.result()
                results_map[result_name] = result
                logger.info(f"Parallel task {result_name} completed in {elapsed:.2f}s")
            except Exception as e:
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
            future = executor.submit(_execute_transfer_with_timing, name, klass, flags)
            futures[future] = name

        future = executor.submit(
            _execute_session_transfer_with_timing,
            "StratigraphyNew",
            transfer_stratigraphy,
            limit,
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
                "Permissions"
            )
            results_map[result_name] = result
            logger.info(f"Task {result_name} completed in {elapsed:.2f}s")
        except Exception as e:
            logger.critical(f"Task Permissions failed: {e}")

    if opts.transfer_major_chemistry:
        message("TRANSFERRING MAJOR CHEMISTRY")
        results = _execute_transfer(MajorChemistryTransferer, flags=flags)
        metrics.major_chemistry_metrics(*results)

    if opts.transfer_radionuclides:
        message("TRANSFERRING RADIONUCLIDES")
        results = _execute_transfer(RadionuclidesTransferer, flags=flags)
        metrics.radionuclides_metrics(*results)

    if opts.transfer_minor_trace_chemistry:
        message("TRANSFERRING MINOR TRACE CHEMISTRY")
        results = _execute_transfer(MinorTraceChemistryTransferer, flags=flags)
        metrics.minor_trace_chemistry_metrics(*results)

    if opts.transfer_field_parameters:
        message("TRANSFERRING FIELD PARAMETERS")
        results = _execute_transfer(FieldParametersTransferer, flags=flags)
        metrics.field_parameters_metrics(*results)

    # =========================================================================
    # PHASE 3: Sensors (Sequential - required before continuous water levels)
    # =========================================================================
    if opts.transfer_sensors:
        message("TRANSFERRING SENSORS")
        results = _execute_transfer(SensorTransferer, flags=flags)
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
            cleanup_locations(session)


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
