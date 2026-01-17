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

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

from db.engine import session_ctx
from db.initialization import recreate_public_schema, sync_search_vector_triggers
from services.util import get_bool_env
from transfers.aquifer_system_transfer import transfer_aquifer_systems
from transfers.geologic_formation_transfer import transfer_geologic_formations
from transfers.permissions_transfer import transfer_permissions
from transfers.stratigraphy_legacy import StratigraphyLegacyTransferer
from transfers.stratigraphy_transfer import transfer_stratigraphy

load_dotenv()

from transfers.waterlevels_transducer_transfer import (
    WaterLevelsContinuousPressureTransferer,
    WaterLevelsContinuousAcousticTransferer,
)

from transfers.metrics import Metrics
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
    cleanup_locations,
)
from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer

from transfers.asset_transfer import AssetTransferer
from transfers.chemistry_sampleinfo import ChemistrySampleInfoTransferer
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
    NMAWaterLevelsContinuousPressureDailyTransferer,
)
from transfers.weather_data import WeatherDataTransferer
from transfers.weather_photos import WeatherPhotosTransferer
from transfers.logger import logger, save_log_to_bucket


def message(msg, pad=10, new_line_at_top=True):
    pad = "*" * pad
    if new_line_at_top:
        logger.info("")
    logger.info(f"{pad} {msg} {pad}")


def _execute_transfer(klass, flags: dict = None):
    """Execute a single transfer class. Thread-safe since each creates its own session."""
    pointids = None
    if os.getenv("TRANSFER_TEST_POINTIDS"):
        pointids = os.getenv("TRANSFER_TEST_POINTIDS").split(",")

    transferer = klass(flags=flags, pointids=pointids)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


def _execute_transfer_with_timing(name: str, klass, flags: dict = None):
    """Execute transfer and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    result = _execute_transfer(klass, flags)
    elapsed = time.time() - start
    logger.info(f"Completed parallel transfer: {name} in {elapsed:.2f}s")
    return name, result, elapsed


def _execute_session_transfer_with_timing(name: str, transfer_func, limit: int):
    """Execute a session-based transfer function and return timing info."""
    start = time.time()
    logger.info(f"Starting parallel transfer: {name}")
    with session_ctx() as session:
        result = transfer_func(session, limit=limit)
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
def transfer_all(metrics, limit=100):
    message("STARTING TRANSFER", new_line_at_top=False)
    if get_bool_env("DROP_AND_REBUILD_DB", False):
        logger.info("Dropping schema and rebuilding database from migrations")
        _drop_and_rebuild_db()
    elif get_bool_env("ERASE_AND_REBUILD", False):
        logger.info("Erase and rebuilding database")
        erase_and_rebuild_db()

    flags = {"TRANSFER_ALL_WELLS": True, "LIMIT": limit}

    # =========================================================================
    # PHASE 1: Foundation (Parallel - these are independent of each other)
    # =========================================================================
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
    use_parallel_wells = get_bool_env("TRANSFER_PARALLEL_WELLS", False)
    if use_parallel_wells:
        logger.info("Using PARALLEL wells transfer")
        transferer = WellTransferer(flags=flags)
        transferer.transfer_parallel()
        results = (transferer.input_df, transferer.cleaned_df, transferer.errors)
    else:
        results = _execute_transfer(WellTransferer, flags=flags)
    metrics.well_metrics(*results)

    # Get transfer flags
    transfer_screens = get_bool_env("TRANSFER_WELL_SCREENS", True)
    transfer_sensors = get_bool_env("TRANSFER_SENSORS", True)
    transfer_contacts = get_bool_env("TRANSFER_CONTACTS", True)
    transfer_waterlevels = get_bool_env("TRANSFER_WATERLEVELS", True)
    transfer_pressure = get_bool_env("TRANSFER_WATERLEVELS_PRESSURE", True)
    transfer_acoustic = get_bool_env("TRANSFER_WATERLEVELS_ACOUSTIC", True)
    transfer_link_ids = get_bool_env("TRANSFER_LINK_IDS", True)
    transfer_groups = get_bool_env("TRANSFER_GROUPS", True)
    transfer_assets = get_bool_env("TRANSFER_ASSETS", False)
    transfer_surface_water_photos = get_bool_env("TRANSFER_SURFACE_WATER_PHOTOS", True)
    transfer_soil_rock_results = get_bool_env("TRANSFER_SOIL_ROCK_RESULTS", True)
    transfer_surface_water_data = get_bool_env("TRANSFER_SURFACE_WATER_DATA", True)
    transfer_hydraulics_data = get_bool_env("TRANSFER_HYDRAULICS_DATA", True)
    transfer_chemistry_sampleinfo = get_bool_env("TRANSFER_CHEMISTRY_SAMPLEINFO", True)
    transfer_major_chemistry = get_bool_env("TRANSFER_MAJOR_CHEMISTRY", True)
    transfer_radionuclides = get_bool_env("TRANSFER_RADIONUCLIDES", True)
    transfer_ngwmn_views = get_bool_env("TRANSFER_NGWMN_VIEWS", True)
    transfer_pressure_daily = get_bool_env("TRANSFER_WATERLEVELS_PRESSURE_DAILY", True)
    transfer_weather_data = get_bool_env("TRANSFER_WEATHER_DATA", True)
    transfer_weather_photos = get_bool_env("TRANSFER_WEATHER_PHOTOS", True)
    transfer_minor_trace_chemistry = get_bool_env(
        "TRANSFER_MINOR_TRACE_CHEMISTRY", True
    )
    transfer_nma_stratigraphy = get_bool_env("TRANSFER_NMA_STRATIGRAPHY", True)
    transfer_associated_data = get_bool_env("TRANSFER_ASSOCIATED_DATA", True)
    use_parallel = get_bool_env("TRANSFER_PARALLEL", True)

    if use_parallel:
        _transfer_parallel(
            metrics,
            flags,
            limit,
            transfer_screens,
            transfer_sensors,
            transfer_contacts,
            transfer_waterlevels,
            transfer_pressure,
            transfer_acoustic,
            transfer_link_ids,
            transfer_groups,
            transfer_assets,
            transfer_surface_water_photos,
            transfer_soil_rock_results,
            transfer_surface_water_data,
            transfer_hydraulics_data,
            transfer_chemistry_sampleinfo,
            transfer_major_chemistry,
            transfer_radionuclides,
            transfer_ngwmn_views,
            transfer_pressure_daily,
            transfer_weather_data,
            transfer_weather_photos,
            transfer_minor_trace_chemistry,
            transfer_nma_stratigraphy,
            transfer_associated_data,
        )
    else:
        _transfer_sequential(
            metrics,
            flags,
            limit,
            transfer_screens,
            transfer_sensors,
            transfer_contacts,
            transfer_waterlevels,
            transfer_pressure,
            transfer_acoustic,
            transfer_link_ids,
            transfer_groups,
            transfer_assets,
            transfer_surface_water_photos,
            transfer_soil_rock_results,
            transfer_surface_water_data,
            transfer_hydraulics_data,
            transfer_chemistry_sampleinfo,
            transfer_major_chemistry,
            transfer_radionuclides,
            transfer_ngwmn_views,
            transfer_pressure_daily,
            transfer_weather_data,
            transfer_weather_photos,
            transfer_minor_trace_chemistry,
            transfer_nma_stratigraphy,
            transfer_associated_data,
        )


def _transfer_parallel(
    metrics,
    flags,
    limit,
    transfer_screens,
    transfer_sensors,
    transfer_contacts,
    transfer_waterlevels,
    transfer_pressure,
    transfer_acoustic,
    transfer_link_ids,
    transfer_groups,
    transfer_assets,
    transfer_surface_water_photos,
    transfer_soil_rock_results,
    transfer_surface_water_data,
    transfer_hydraulics_data,
    transfer_chemistry_sampleinfo,
    transfer_major_chemistry,
    transfer_radionuclides,
    transfer_ngwmn_views,
    transfer_pressure_daily,
    transfer_weather_data,
    transfer_weather_photos,
    transfer_minor_trace_chemistry,
    transfer_nma_stratigraphy,
    transfer_associated_data,
):
    """Execute transfers in parallel where possible."""
    message("PARALLEL TRANSFER GROUP 1")

    # =========================================================================
    # PHASE 2: Parallel Group 1 (Independent transfers after wells)
    # =========================================================================
    parallel_tasks_1 = []

    if transfer_screens:
        parallel_tasks_1.append(("WellScreens", WellScreenTransferer, flags))
    if transfer_contacts:
        parallel_tasks_1.append(("Contacts", ContactTransfer, flags))
    if transfer_waterlevels:
        parallel_tasks_1.append(("WaterLevels", WaterLevelTransferer, flags))
    if transfer_link_ids:
        parallel_tasks_1.append(("LinkIdsWellData", LinkIdsWellDataTransferer, flags))
        parallel_tasks_1.append(
            ("LinkIdsLocation", LinkIdsLocationDataTransferer, flags)
        )
    if transfer_groups:
        parallel_tasks_1.append(("Groups", ProjectGroupTransferer, flags))
    if transfer_surface_water_photos:
        parallel_tasks_1.append(
            ("SurfaceWaterPhotos", SurfaceWaterPhotosTransferer, flags)
        )
    if transfer_soil_rock_results:
        parallel_tasks_1.append(("SoilRockResults", SoilRockResultsTransferer, flags))
    if transfer_weather_photos:
        parallel_tasks_1.append(("WeatherPhotos", WeatherPhotosTransferer, flags))
    if transfer_assets:
        parallel_tasks_1.append(("Assets", AssetTransferer, flags))
    if transfer_associated_data:
        parallel_tasks_1.append(("AssociatedData", AssociatedDataTransferer, flags))
    if transfer_surface_water_data:
        parallel_tasks_1.append(("SurfaceWaterData", SurfaceWaterDataTransferer, flags))
    if transfer_hydraulics_data:
        parallel_tasks_1.append(("HydraulicsData", HydraulicsDataTransferer, flags))
    if transfer_chemistry_sampleinfo:
        parallel_tasks_1.append(
            ("ChemistrySampleInfo", ChemistrySampleInfoTransferer, flags)
        )
    if transfer_ngwmn_views:
        parallel_tasks_1.append(
            ("NGWMNWellConstruction", NGWMNWellConstructionTransferer, flags)
        )
        parallel_tasks_1.append(("NGWMNWaterLevels", NGWMNWaterLevelsTransferer, flags))
        parallel_tasks_1.append(("NGWMNLithology", NGWMNLithologyTransferer, flags))
    if transfer_pressure_daily:
        parallel_tasks_1.append(
            (
                "WaterLevelsPressureDaily",
                NMAWaterLevelsContinuousPressureDailyTransferer,
                flags,
            )
        )
    if transfer_weather_data:
        parallel_tasks_1.append(("WeatherData", WeatherDataTransferer, flags))

    # Track results for metrics
    results_map = {}

    # Execute parallel group 1
    with ThreadPoolExecutor(max_workers=min(8, len(parallel_tasks_1) + 2)) as executor:
        futures = {}

        # Submit class-based transfers
        for name, klass, task_flags in parallel_tasks_1:
            future = executor.submit(
                _execute_transfer_with_timing, name, klass, task_flags
            )
            futures[future] = name

        # Submit session-based transfers
        if transfer_nma_stratigraphy:
            future = executor.submit(
                _execute_transfer_with_timing,
                "Stratigraphy",
                StratigraphyLegacyTransferer,
                flags,
            )
            futures[future] = "StratigraphyLegacy"

        future = executor.submit(
            _execute_session_transfer_with_timing,
            "Stratigraphy",
            transfer_stratigraphy,
            limit,
        )
        futures[future] = "Stratigraphy"

        future = executor.submit(_execute_permissions_with_timing, "Permissions")
        futures[future] = "Permissions"

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
    if "Stratigraphy" in results_map and results_map["Stratigraphy"]:
        metrics.stratigraphy_metrics(*results_map["Stratigraphy"])
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
    if transfer_major_chemistry:
        message("TRANSFERRING MAJOR CHEMISTRY")
        results = _execute_transfer(MajorChemistryTransferer, flags=flags)
        metrics.major_chemistry_metrics(*results)

    if transfer_radionuclides:
        message("TRANSFERRING RADIONUCLIDES")
        results = _execute_transfer(RadionuclidesTransferer, flags=flags)
        metrics.radionuclides_metrics(*results)

    if transfer_minor_trace_chemistry:
        message("TRANSFERRING MINOR TRACE CHEMISTRY")
        results = _execute_transfer(MinorTraceChemistryTransferer, flags=flags)
        metrics.minor_trace_chemistry_metrics(*results)

    # =========================================================================
    # PHASE 3: Sensors (Sequential - required before continuous water levels)
    # =========================================================================
    if transfer_sensors:
        message("TRANSFERRING SENSORS")
        results = _execute_transfer(SensorTransferer, flags=flags)
        metrics.sensor_metrics(*results)

    # =========================================================================
    # PHASE 4: Parallel Group 2 (Continuous water levels - after sensors)
    # =========================================================================
    if transfer_pressure or transfer_acoustic:
        message("PARALLEL TRANSFER GROUP 2 (Continuous Water Levels)")

        parallel_tasks_2 = []
        if transfer_pressure:
            parallel_tasks_2.append(
                ("Pressure", WaterLevelsContinuousPressureTransferer, flags)
            )
        if transfer_acoustic:
            parallel_tasks_2.append(
                ("Acoustic", WaterLevelsContinuousAcousticTransferer, flags)
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for name, klass, task_flags in parallel_tasks_2:
                future = executor.submit(
                    _execute_transfer_with_timing, name, klass, task_flags
                )
                futures[future] = name

            for future in as_completed(futures):
                name = futures[future]
                try:
                    result_name, result, elapsed = future.result()
                    results_map[result_name] = result
                    logger.info(
                        f"Parallel task {result_name} completed in {elapsed:.2f}s"
                    )
                except Exception as e:
                    logger.critical(f"Parallel task {name} failed: {e}")

        if "Pressure" in results_map and results_map["Pressure"]:
            metrics.pressure_metrics(*results_map["Pressure"])
        if "Acoustic" in results_map and results_map["Acoustic"]:
            metrics.acoustic_metrics(*results_map["Acoustic"])


def _transfer_sequential(
    metrics,
    flags,
    limit,
    transfer_screens,
    transfer_sensors,
    transfer_contacts,
    transfer_waterlevels,
    transfer_pressure,
    transfer_acoustic,
    transfer_link_ids,
    transfer_groups,
    transfer_assets,
    transfer_surface_water_photos,
    transfer_soil_rock_results,
    transfer_surface_water_data,
    transfer_hydraulics_data,
    transfer_chemistry_sampleinfo,
    transfer_major_chemistry,
    transfer_radionuclides,
    transfer_ngwmn_views,
    transfer_pressure_daily,
    transfer_weather_data,
    transfer_weather_photos,
    transfer_minor_trace_chemistry,
    transfer_nma_stratigraphy,
    transfer_associated_data,
):
    """Original sequential transfer logic."""
    if transfer_screens:
        message("TRANSFERRING WELL SCREENS")
        results = _execute_transfer(WellScreenTransferer, flags=flags)
        metrics.well_screen_metrics(*results)

    if transfer_sensors:
        message("TRANSFERRING SENSORS")
        results = _execute_transfer(SensorTransferer, flags=flags)
        metrics.sensor_metrics(*results)

    if transfer_contacts:
        message("TRANSFERRING CONTACTS")
        results = _execute_transfer(ContactTransfer, flags=flags)
        metrics.contact_metrics(*results)

    message("TRANSFERRING PERMISSIONS")
    with session_ctx() as session:
        transfer_permissions(session)

    if transfer_nma_stratigraphy:
        message("TRANSFERRING NMA STRATIGRAPHY")
        results = _execute_transfer(StratigraphyLegacyTransferer, flags=flags)
        metrics.nma_stratigraphy_metrics(*results)

    message("TRANSFERRING STRATIGRAPHY")
    with session_ctx() as session:
        results = transfer_stratigraphy(session, limit=limit)
        metrics.stratigraphy_metrics(*results)

    if transfer_waterlevels:
        message("TRANSFERRING WATER LEVELS")
        results = _execute_transfer(WaterLevelTransferer, flags=flags)
        metrics.water_level_metrics(*results)

    if transfer_link_ids:
        message("TRANSFERRING LINK IDS")
        results = _execute_transfer(LinkIdsWellDataTransferer, flags=flags)
        metrics.welldata_link_ids_metrics(*results)
        results = _execute_transfer(LinkIdsLocationDataTransferer, flags=flags)
        metrics.location_link_ids_metrics(*results)

    if transfer_groups:
        message("TRANSFERRING GROUPS")
        results = _execute_transfer(ProjectGroupTransferer, flags=flags)
        metrics.group_metrics(*results)

    if transfer_surface_water_photos:
        message("TRANSFERRING SURFACE WATER PHOTOS")
        results = _execute_transfer(SurfaceWaterPhotosTransferer, flags=flags)
        metrics.surface_water_photos_metrics(*results)

    if transfer_soil_rock_results:
        message("TRANSFERRING SOIL ROCK RESULTS")
        results = _execute_transfer(SoilRockResultsTransferer, flags=flags)
        metrics.soil_rock_results_metrics(*results)

    if transfer_weather_photos:
        message("TRANSFERRING WEATHER PHOTOS")
        results = _execute_transfer(WeatherPhotosTransferer, flags=flags)
        metrics.weather_photos_metrics(*results)

    if transfer_assets:
        message("TRANSFERRING ASSETS")
        results = _execute_transfer(AssetTransferer, flags=flags)
        metrics.asset_metrics(*results)

    if transfer_associated_data:
        message("TRANSFERRING ASSOCIATED DATA")
        results = _execute_transfer(AssociatedDataTransferer, flags=flags)
        metrics.associated_data_metrics(*results)

    if transfer_surface_water_data:
        message("TRANSFERRING SURFACE WATER DATA")
        results = _execute_transfer(SurfaceWaterDataTransferer, flags=flags)
        metrics.surface_water_data_metrics(*results)

    if transfer_hydraulics_data:
        message("TRANSFERRING HYDRAULICS DATA")
        results = _execute_transfer(HydraulicsDataTransferer, flags=flags)
        metrics.hydraulics_data_metrics(*results)

    if transfer_chemistry_sampleinfo:
        message("TRANSFERRING CHEMISTRY SAMPLEINFO")
        results = _execute_transfer(ChemistrySampleInfoTransferer, flags=flags)
        metrics.chemistry_sampleinfo_metrics(*results)

    if transfer_major_chemistry:
        message("TRANSFERRING MAJOR CHEMISTRY")
        results = _execute_transfer(MajorChemistryTransferer, flags=flags)
        metrics.major_chemistry_metrics(*results)

    if transfer_radionuclides:
        message("TRANSFERRING RADIONUCLIDES")
        results = _execute_transfer(RadionuclidesTransferer, flags=flags)
        metrics.radionuclides_metrics(*results)

    if transfer_ngwmn_views:
        message("TRANSFERRING NGWMN WELL CONSTRUCTION")
        results = _execute_transfer(NGWMNWellConstructionTransferer, flags=flags)
        metrics.ngwmn_well_construction_metrics(*results)
        message("TRANSFERRING NGWMN WATER LEVELS")
        results = _execute_transfer(NGWMNWaterLevelsTransferer, flags=flags)
        metrics.ngwmn_water_levels_metrics(*results)
        message("TRANSFERRING NGWMN LITHOLOGY")
        results = _execute_transfer(NGWMNLithologyTransferer, flags=flags)
        metrics.ngwmn_lithology_metrics(*results)

    if transfer_pressure_daily:
        message("TRANSFERRING WATER LEVELS PRESSURE DAILY")
        results = _execute_transfer(
            NMAWaterLevelsContinuousPressureDailyTransferer, flags=flags
        )
        metrics.waterlevels_pressure_daily_metrics(*results)

    if transfer_weather_data:
        message("TRANSFERRING WEATHER DATA")
        results = _execute_transfer(WeatherDataTransferer, flags=flags)
        metrics.weather_data_metrics(*results)

    if transfer_minor_trace_chemistry:
        message("TRANSFERRING MINOR TRACE CHEMISTRY")
        results = _execute_transfer(MinorTraceChemistryTransferer, flags=flags)
        metrics.minor_trace_chemistry_metrics(*results)

    if transfer_pressure:
        message("TRANSFERRING WATER LEVELS PRESSURE")
        results = _execute_transfer(
            WaterLevelsContinuousPressureTransferer, flags=flags
        )
        metrics.pressure_metrics(*results)

    if transfer_acoustic:
        message("TRANSFERRING WATER LEVELS ACOUSTIC")
        results = _execute_transfer(
            WaterLevelsContinuousAcousticTransferer, flags=flags
        )
        metrics.acoustic_metrics(*results)

    message("CLEANING UP LOCATIONS")
    with session_ctx() as session:
        cleanup_locations(session)


def main():
    message("START--------------------------------------")
    limit = int(os.getenv("TRANSFER_LIMIT", 1000))
    metrics = Metrics()

    transfer_all(metrics, limit=limit)

    metrics.close()
    metrics.save_to_storage_bucket()
    save_log_to_bucket()
    message("END--------------------------------------")


if __name__ == "__main__":
    main()
# ============= EOF =============================================
