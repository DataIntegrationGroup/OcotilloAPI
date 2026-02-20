from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from transfers.associated_data import AssociatedDataTransferer
from transfers.chemistry_sampleinfo import ChemistrySampleInfoTransferer
from transfers.contact_transfer import ContactTransfer
from transfers.field_parameters_transfer import FieldParametersTransferer
from transfers.group_transfer import ProjectGroupTransferer
from transfers.hydraulicsdata import HydraulicsDataTransferer
from transfers.major_chemistry import MajorChemistryTransferer
from transfers.minor_trace_chemistry_transfer import MinorTraceChemistryTransferer
from transfers.ngwmn_views import (
    NGWMNLithologyTransferer,
    NGWMNWaterLevelsTransferer,
    NGWMNWellConstructionTransferer,
)
from transfers.radionuclides import RadionuclidesTransferer
from transfers.sensor_transfer import SensorTransferer
from transfers.soil_rock_results import SoilRockResultsTransferer
from transfers.stratigraphy_legacy import StratigraphyLegacyTransferer
from transfers.surface_water_data import SurfaceWaterDataTransferer
from transfers.surface_water_photos import SurfaceWaterPhotosTransferer
from transfers.util import read_csv
from transfers.waterlevels_transfer import WaterLevelTransferer
from transfers.waterlevelscontinuous_pressure_daily import (
    NMA_WaterLevelsContinuous_Pressure_DailyTransferer,
)
from transfers.weather_data import WeatherDataTransferer
from transfers.weather_photos import WeatherPhotosTransferer
from transfers.well_transfer import WellScreenTransferer, WellTransferer
from db import (
    Contact,
    Group,
    NMA_AssociatedData,
    NMA_Chemistry_SampleInfo,
    NMA_FieldParameters,
    NMA_HydraulicsData,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
    NMA_Radionuclides,
    NMA_Soil_Rock_Results,
    NMA_Stratigraphy,
    NMA_SurfaceWaterData,
    NMA_SurfaceWaterPhotos,
    NMA_WaterLevelsContinuous_Pressure_Daily,
    NMA_WeatherData,
    NMA_WeatherPhotos,
    NMA_view_NGWMN_Lithology,
    NMA_view_NGWMN_WaterLevels,
    NMA_view_NGWMN_WellConstruction,
    Observation,
    Sensor,
    Thing,
    WellScreen,
)
from transfers.transfer_results_types import (
    AssociatedDataTransferResult,
    ChemistrySampleInfoTransferResult,
    DiversionOfSurfaceWaterTransferResult,
    EphemeralStreamsTransferResult,
    EquipmentTransferResult,
    FieldParametersTransferResult,
    HydraulicsDataTransferResult,
    LakePondReservoirTransferResult,
    MajorChemistryTransferResult,
    MetStationsTransferResult,
    MinorTraceChemistryTransferResult,
    NGWMNLithologyTransferResult,
    NGWMNWaterLevelsTransferResult,
    NGWMNWellConstructionTransferResult,
    OtherSiteTypesTransferResult,
    OutfallWastewaterReturnFlowTransferResult,
    OwnersDataTransferResult,
    PerennialStreamsTransferResult,
    PressureDailyTransferResult,
    ProjectsTransferResult,
    RadionuclidesTransferResult,
    RockSampleLocationsTransferResult,
    SoilGasSampleLocationsTransferResult,
    SoilRockResultsTransferResult,
    SpringsTransferResult,
    StratigraphyTransferResult,
    SurfaceWaterDataTransferResult,
    SurfaceWaterPhotosTransferResult,
    TransferResult,
    WaterLevelsTransferResult,
    WeatherDataTransferResult,
    WeatherPhotosTransferResult,
    WellDataTransferResult,
    WellScreensTransferResult,
)


@dataclass(frozen=True)
class TransferComparisonSpec:
    transfer_name: str
    result_cls: type[TransferResult]
    source_csv: str
    source_key_column: str
    destination_model: Any
    destination_key_column: str
    source_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None
    destination_where: Callable[[Any], Any] | None = None
    agreed_row_counter: Callable[[], int] | None = None


def _location_site_filter(site_type: str) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def _f(df: pd.DataFrame) -> pd.DataFrame:
        if "SiteType" not in df.columns:
            return df.iloc[0:0]
        return df[df["SiteType"] == site_type]

    return _f


def _agreed_rows_from_transferer(transferer_cls) -> int:
    transferer = transferer_cls()
    _, cleaned_df = transferer._get_dfs()
    return int(len(cleaned_df))


def _agreed_rows_location(site_type: str) -> int:
    df = read_csv("Location")
    df = df[df["SiteType"] == site_type]
    df = df[df["Easting"].notna() & df["Northing"].notna()]
    return int(len(df))


TRANSFER_COMPARISON_SPECS: list[TransferComparisonSpec] = [
    TransferComparisonSpec(
        "WellData",
        WellDataTransferResult,
        "WellData",
        "WellID",
        Thing,
        "nma_pk_welldata",
        destination_where=lambda m: m.thing_type == "water well",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(WellTransferer),
    ),
    TransferComparisonSpec(
        "WellScreens",
        WellScreensTransferResult,
        "WellScreens",
        "GlobalID",
        WellScreen,
        "nma_pk_wellscreens",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(WellScreenTransferer),
    ),
    TransferComparisonSpec(
        "OwnersData",
        OwnersDataTransferResult,
        "OwnersData",
        "OwnerKey",
        Contact,
        "nma_pk_owners",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(ContactTransfer),
    ),
    TransferComparisonSpec(
        "WaterLevels",
        WaterLevelsTransferResult,
        "WaterLevels",
        "GlobalID",
        Observation,
        "nma_pk_waterlevels",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(WaterLevelTransferer),
    ),
    TransferComparisonSpec(
        "Equipment",
        EquipmentTransferResult,
        "Equipment",
        "GlobalID",
        Sensor,
        "nma_pk_equipment",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(SensorTransferer),
    ),
    TransferComparisonSpec(
        "Projects",
        ProjectsTransferResult,
        "Projects",
        "Project",
        Group,
        "name",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(ProjectGroupTransferer),
    ),
    TransferComparisonSpec(
        "SurfaceWaterPhotos",
        SurfaceWaterPhotosTransferResult,
        "SurfaceWaterPhotos",
        "GlobalID",
        NMA_SurfaceWaterPhotos,
        "global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            SurfaceWaterPhotosTransferer
        ),
    ),
    TransferComparisonSpec(
        "Soil_Rock_Results",
        SoilRockResultsTransferResult,
        "Soil_Rock_Results",
        "Point_ID",
        NMA_Soil_Rock_Results,
        "nma_point_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            SoilRockResultsTransferer
        ),
    ),
    TransferComparisonSpec(
        "WeatherPhotos",
        WeatherPhotosTransferResult,
        "WeatherPhotos",
        "GlobalID",
        NMA_WeatherPhotos,
        "global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            WeatherPhotosTransferer
        ),
    ),
    TransferComparisonSpec(
        "AssociatedData",
        AssociatedDataTransferResult,
        "AssociatedData",
        "AssocID",
        NMA_AssociatedData,
        "nma_assoc_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            AssociatedDataTransferer
        ),
    ),
    TransferComparisonSpec(
        "SurfaceWaterData",
        SurfaceWaterDataTransferResult,
        "SurfaceWaterData",
        "OBJECTID",
        NMA_SurfaceWaterData,
        "object_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            SurfaceWaterDataTransferer
        ),
    ),
    TransferComparisonSpec(
        "HydraulicsData",
        HydraulicsDataTransferResult,
        "HydraulicsData",
        "GlobalID",
        NMA_HydraulicsData,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            HydraulicsDataTransferer
        ),
    ),
    TransferComparisonSpec(
        "Chemistry_SampleInfo",
        ChemistrySampleInfoTransferResult,
        "Chemistry_SampleInfo",
        "SamplePtID",
        NMA_Chemistry_SampleInfo,
        "nma_sample_pt_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            ChemistrySampleInfoTransferer
        ),
    ),
    TransferComparisonSpec(
        "view_NGWMN_WellConstruction",
        NGWMNWellConstructionTransferResult,
        "view_NGWMN_WellConstruction",
        "PointID",
        NMA_view_NGWMN_WellConstruction,
        "point_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            NGWMNWellConstructionTransferer
        ),
    ),
    TransferComparisonSpec(
        "view_NGWMN_WaterLevels",
        NGWMNWaterLevelsTransferResult,
        "view_NGWMN_WaterLevels",
        "PointID",
        NMA_view_NGWMN_WaterLevels,
        "point_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            NGWMNWaterLevelsTransferer
        ),
    ),
    TransferComparisonSpec(
        "view_NGWMN_Lithology",
        NGWMNLithologyTransferResult,
        "view_NGWMN_Lithology",
        "PointID",
        NMA_view_NGWMN_Lithology,
        "point_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            NGWMNLithologyTransferer
        ),
    ),
    TransferComparisonSpec(
        "WaterLevelsContinuous_Pressure_Daily",
        PressureDailyTransferResult,
        "WaterLevelsContinuous_Pressure_Daily",
        "GlobalID",
        NMA_WaterLevelsContinuous_Pressure_Daily,
        "global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            NMA_WaterLevelsContinuous_Pressure_DailyTransferer
        ),
    ),
    TransferComparisonSpec(
        "WeatherData",
        WeatherDataTransferResult,
        "WeatherData",
        "OBJECTID",
        NMA_WeatherData,
        "object_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(WeatherDataTransferer),
    ),
    TransferComparisonSpec(
        "Stratigraphy",
        StratigraphyTransferResult,
        "Stratigraphy",
        "GlobalID",
        NMA_Stratigraphy,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            StratigraphyLegacyTransferer
        ),
    ),
    TransferComparisonSpec(
        "MajorChemistry",
        MajorChemistryTransferResult,
        "MajorChemistry",
        "GlobalID",
        NMA_MajorChemistry,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            MajorChemistryTransferer
        ),
    ),
    TransferComparisonSpec(
        "Radionuclides",
        RadionuclidesTransferResult,
        "Radionuclides",
        "GlobalID",
        NMA_Radionuclides,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            RadionuclidesTransferer
        ),
    ),
    TransferComparisonSpec(
        "MinorandTraceChemistry",
        MinorTraceChemistryTransferResult,
        "MinorandTraceChemistry",
        "GlobalID",
        NMA_MinorTraceChemistry,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            MinorTraceChemistryTransferer
        ),
    ),
    TransferComparisonSpec(
        "FieldParameters",
        FieldParametersTransferResult,
        "FieldParameters",
        "GlobalID",
        NMA_FieldParameters,
        "nma_global_id",
        agreed_row_counter=lambda: _agreed_rows_from_transferer(
            FieldParametersTransferer
        ),
    ),
    TransferComparisonSpec(
        "Springs",
        SpringsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("SP"),
        destination_where=lambda m: m.thing_type == "spring",
        agreed_row_counter=lambda: _agreed_rows_location("SP"),
    ),
    TransferComparisonSpec(
        "PerennialStreams",
        PerennialStreamsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("PS"),
        destination_where=lambda m: m.thing_type == "perennial stream",
        agreed_row_counter=lambda: _agreed_rows_location("PS"),
    ),
    TransferComparisonSpec(
        "EphemeralStreams",
        EphemeralStreamsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("ES"),
        destination_where=lambda m: m.thing_type == "ephemeral stream",
        agreed_row_counter=lambda: _agreed_rows_location("ES"),
    ),
    TransferComparisonSpec(
        "MetStations",
        MetStationsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("M"),
        destination_where=lambda m: m.thing_type == "meteorological station",
        agreed_row_counter=lambda: _agreed_rows_location("M"),
    ),
    TransferComparisonSpec(
        "RockSampleLocations",
        RockSampleLocationsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("R"),
        destination_where=lambda m: m.thing_type == "rock sample location",
        agreed_row_counter=lambda: _agreed_rows_location("R"),
    ),
    TransferComparisonSpec(
        "DiversionOfSurfaceWater",
        DiversionOfSurfaceWaterTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("D"),
        destination_where=lambda m: m.thing_type == "diversion of surface water, etc.",
        agreed_row_counter=lambda: _agreed_rows_location("D"),
    ),
    TransferComparisonSpec(
        "LakePondReservoir",
        LakePondReservoirTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("L"),
        destination_where=lambda m: m.thing_type == "lake, pond or reservoir",
        agreed_row_counter=lambda: _agreed_rows_location("L"),
    ),
    TransferComparisonSpec(
        "SoilGasSampleLocations",
        SoilGasSampleLocationsTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("S"),
        destination_where=lambda m: m.thing_type == "soil gas sample location",
        agreed_row_counter=lambda: _agreed_rows_location("S"),
    ),
    TransferComparisonSpec(
        "OtherSiteTypes",
        OtherSiteTypesTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("OT"),
        destination_where=lambda m: m.thing_type == "other",
        agreed_row_counter=lambda: _agreed_rows_location("OT"),
    ),
    TransferComparisonSpec(
        "OutfallWastewaterReturnFlow",
        OutfallWastewaterReturnFlowTransferResult,
        "Location",
        "LocationId",
        Thing,
        "nma_pk_location",
        source_filter=_location_site_filter("O"),
        destination_where=lambda m: m.thing_type
        == "outfall of wastewater or return flow",
        agreed_row_counter=lambda: _agreed_rows_location("O"),
    ),
]
