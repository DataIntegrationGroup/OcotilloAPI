from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TransferResult:
    transfer_name: str
    source_csv: str
    source_key_column: str
    destination_model: str
    destination_key_column: str
    source_row_count: int = 0
    agreed_transfer_row_count: int = 0
    source_keyed_row_count: int = 0
    source_key_count: int = 0
    source_duplicate_key_row_count: int = 0
    destination_row_count: int = 0
    destination_keyed_row_count: int = 0
    destination_key_count: int = 0
    destination_duplicate_key_row_count: int = 0
    matched_key_count: int = 0
    missing_in_destination_count: int = 0
    extra_in_destination_count: int = 0
    transferred_agreed_row_count: int = 0
    missing_agreed_row_count: int = 0
    missing_in_destination_sample: list[str] = field(default_factory=list)
    extra_in_destination_sample: list[str] = field(default_factory=list)


@dataclass
class TransferComparisonResults:
    generated_at: str
    results: dict[str, TransferResult]


_RESULT_CLASS_NAMES = [
    "WellData",
    "WellScreens",
    "OwnersData",
    "Permissions",
    "WaterLevels",
    "Equipment",
    "Projects",
    "SurfaceWaterPhotos",
    "SoilRockResults",
    "WeatherPhotos",
    "AssociatedData",
    "SurfaceWaterData",
    "HydraulicsData",
    "ChemistrySampleInfo",
    "NGWMNWellConstruction",
    "NGWMNWaterLevels",
    "NGWMNLithology",
    "PressureDaily",
    "WeatherData",
    "Stratigraphy",
    "MajorChemistry",
    "Radionuclides",
    "MinorTraceChemistry",
    "FieldParameters",
    "Springs",
    "PerennialStreams",
    "EphemeralStreams",
    "MetStations",
    "RockSampleLocations",
    "DiversionOfSurfaceWater",
    "LakePondReservoir",
    "SoilGasSampleLocations",
    "OtherSiteTypes",
    "OutfallWastewaterReturnFlow",
]

for _name in _RESULT_CLASS_NAMES:
    globals()[f"{_name}TransferResult"] = type(
        f"{_name}TransferResult", (TransferResult,), {}
    )


__all__ = [
    "TransferResult",
    "TransferComparisonResults",
    *[f"{name}TransferResult" for name in _RESULT_CLASS_NAMES],
]
