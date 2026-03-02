from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

import pandas as pd

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
    PermissionHistory,
    Sensor,
    Thing,
    WellScreen,
    Location,
    LocationThingAssociation,
)
from db.engine import session_ctx
from transfers.contact_transfer import (
    _get_organization,
    _safe_make_name,
    _select_ownerkey_col,
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
    PermissionsTransferResult,
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
from transfers.util import (
    filter_non_transferred_wells,
    filter_by_valid_measuring_agency,
    filter_to_valid_point_ids,
    get_transferable_wells,
    get_transfers_data_path,
    lexicon_mapper,
    read_csv,
    replace_nans,
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
    agreed_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None
    destination_where: Callable[[Any], Any] | None = None
    option_field: str | None = None


def _location_site_filter(site_type: str) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def _f(df: pd.DataFrame) -> pd.DataFrame:
        if "SiteType" not in df.columns:
            return df.iloc[0:0]
        return df[df["SiteType"] == site_type]

    return _f


def _chemistry_sampleinfo_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror ChemistrySampleInfoTransferer filters:
    # 1) valid LocationId that resolves to a Thing via LocationThingAssociation
    # 2) valid UUID SamplePtID
    if "LocationId" not in df.columns or "SamplePtID" not in df.columns:
        return df.iloc[0:0]

    with session_ctx() as session:
        rows = (
            session.query(Location.nma_pk_location)
            .join(
                LocationThingAssociation,
                Location.id == LocationThingAssociation.location_id,
            )
            .filter(Location.nma_pk_location.isnot(None))
            .all()
        )
        valid_location_ids = {
            str(nma_pk_location).strip().lower() for (nma_pk_location,) in rows
        }

    def _normalize_location(value: Any) -> str | None:
        if pd.isna(value):
            return None
        text = str(value).strip().lower()
        return text or None

    def _is_valid_uuid(value: Any) -> bool:
        if pd.isna(value):
            return False
        try:
            UUID(str(value))
        except (TypeError, ValueError):
            return False
        return True

    location_mask = df["LocationId"].apply(_normalize_location).isin(valid_location_ids)
    sample_pt_mask = df["SamplePtID"].apply(_is_valid_uuid)
    return df[location_mask & sample_pt_mask].copy()


def _chemistry_child_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror ChemistryTransferer._filter_to_valid_sample_infos:
    # keep only rows whose SamplePtID resolves to an existing ChemistrySampleInfo.
    if "SamplePtID" not in df.columns:
        return df.iloc[0:0]

    with session_ctx() as session:
        rows = (
            session.query(NMA_Chemistry_SampleInfo.nma_sample_pt_id)
            .filter(NMA_Chemistry_SampleInfo.nma_sample_pt_id.isnot(None))
            .all()
        )
        valid_sample_pt_ids = {sample_pt_id for (sample_pt_id,) in rows}

    def _uuid_or_none(value: Any) -> UUID | None:
        if pd.isna(value):
            return None
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    sample_pt_mask = df["SamplePtID"].map(_uuid_or_none).isin(valid_sample_pt_ids)
    return df[sample_pt_mask].copy()


def _waterlevels_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror WaterLevelTransferer._get_dfs filtering stage.
    cleaned_df = replace_nans(df.copy())
    cleaned_df = filter_to_valid_point_ids(cleaned_df)
    cleaned_df = filter_by_valid_measuring_agency(cleaned_df)

    # Mirror WaterLevelTransferer behavior for observation creation:
    # rows whose mapped LevelStatus indicates a destroyed well only create
    # FieldEvent notes and intentionally do not create observations.
    def _is_destroyed(level_status: Any) -> bool:
        if pd.isna(level_status):
            return False

        value = level_status
        if value == "X?":
            value = "X"
        mapped = lexicon_mapper.map_value(f"LU_LevelStatus:{value}")
        return (
            mapped
            == "Well was destroyed (no subsequent water levels should be recorded)"
        )

    if "LevelStatus" in cleaned_df.columns:
        cleaned_df = cleaned_df[~cleaned_df["LevelStatus"].map(_is_destroyed)]

    return cleaned_df


def _equipment_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror SensorTransferer._get_dfs filtering stage.
    cleaned_df = df.copy()
    cleaned_df.columns = cleaned_df.columns.str.replace(" ", "_")
    if "SerialNo" in cleaned_df.columns:
        cleaned_df = cleaned_df[cleaned_df["SerialNo"].notna()]
    else:
        return cleaned_df.iloc[0:0]
    cleaned_df = filter_to_valid_point_ids(cleaned_df)
    cleaned_df = replace_nans(cleaned_df)
    return cleaned_df


def _wellscreens_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror WellChunkTransferer._get_dfs used by WellScreenTransferer.
    cleaned_df = replace_nans(df.copy())
    cleaned_df = filter_to_valid_point_ids(cleaned_df)
    return cleaned_df


def _welldata_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror WellTransferer._get_dfs filtering stage.
    if "LocationId" not in df.columns:
        return df.iloc[0:0]

    cleaned_df = df.copy()
    ldf = read_csv("Location")
    ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1, errors="ignore")
    cleaned_df = cleaned_df.join(ldf.set_index("LocationId"), on="LocationId")

    if "SiteType" in cleaned_df.columns:
        cleaned_df = cleaned_df[cleaned_df["SiteType"] == "GW"]
    else:
        return cleaned_df.iloc[0:0]

    if "Easting" in cleaned_df.columns and "Northing" in cleaned_df.columns:
        cleaned_df = cleaned_df[
            cleaned_df["Easting"].notna() & cleaned_df["Northing"].notna()
        ]
    else:
        return cleaned_df.iloc[0:0]

    cleaned_df = replace_nans(cleaned_df)
    cleaned_df = get_transferable_wells(cleaned_df)
    cleaned_df = filter_non_transferred_wells(cleaned_df)

    if "PointID" not in cleaned_df.columns:
        return cleaned_df.iloc[0:0]

    # Match WellTransferer behavior: skip every duplicated PointID.
    dupes = cleaned_df["PointID"].duplicated(keep=False)
    if dupes.any():
        dup_ids = set(cleaned_df.loc[dupes, "PointID"])
        cleaned_df = cleaned_df[~cleaned_df["PointID"].isin(dup_ids)]

    return cleaned_df.sort_values(by=["PointID"])


def _stratigraphy_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror StratigraphyLegacyTransferer._get_dfs filtering stage.
    cleaned_df = replace_nans(df.copy())
    cleaned_df = filter_to_valid_point_ids(cleaned_df)
    return cleaned_df


def _hydraulics_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror HydraulicsDataTransferer._filter_to_valid_things:
    # keep only rows whose PointID exists in Thing.name.
    if "PointID" not in df.columns:
        return df.iloc[0:0]

    with session_ctx() as session:
        thing_names = {
            name
            for (name,) in session.query(Thing.name)
            .filter(Thing.name.isnot(None))
            .all()
        }

    return df[df["PointID"].isin(thing_names)].copy()


def _ngwmn_waterlevels_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror NGWMNWaterLevelsTransferer dedupe key:
    # conflict columns are (PointID, DateMeasured), with later rows winning.
    if "PointID" not in df.columns or "DateMeasured" not in df.columns:
        return df.iloc[0:0]

    dedupe_df = df.copy()
    dedupe_df["_pointid_norm"] = dedupe_df["PointID"].astype(str)
    parsed_dates = pd.to_datetime(dedupe_df["DateMeasured"], errors="coerce")
    dedupe_df["_date_measured_norm"] = parsed_dates.dt.date
    # Match transfer _dedupe_rows(..., include_missing=True):
    # rows with missing key parts are not deduped.
    missing_key_mask = (
        dedupe_df["_pointid_norm"].isna() | dedupe_df["_date_measured_norm"].isna()
    )
    non_missing = dedupe_df.loc[~missing_key_mask].drop_duplicates(
        subset=["_pointid_norm", "_date_measured_norm"], keep="last"
    )
    missing = dedupe_df.loc[missing_key_mask]
    out = pd.concat([non_missing, missing], axis=0)
    return out.drop(columns=["_pointid_norm", "_date_measured_norm"])


def _ngwmn_wellconstruction_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror NGWMNWellConstructionTransferer dedupe key:
    # conflict columns are (PointID, CasingTop, ScreenTop), with later rows winning.
    required = {"PointID", "CasingTop", "ScreenTop"}
    if not required.issubset(df.columns):
        return df.iloc[0:0]

    def _float_or_none(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            import re

            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
        return None

    dedupe_df = df.copy()
    dedupe_df["_pointid_norm"] = dedupe_df["PointID"].astype(str)
    dedupe_df["_casing_top_norm"] = dedupe_df["CasingTop"].map(_float_or_none)
    dedupe_df["_screen_top_norm"] = dedupe_df["ScreenTop"].map(_float_or_none)
    # Match transfer _dedupe_rows(..., include_missing=True):
    # rows with missing key parts are not deduped.
    missing_key_mask = (
        dedupe_df["_pointid_norm"].isna()
        | dedupe_df["_casing_top_norm"].isna()
        | dedupe_df["_screen_top_norm"].isna()
    )
    non_missing = dedupe_df.loc[~missing_key_mask].drop_duplicates(
        subset=["_pointid_norm", "_casing_top_norm", "_screen_top_norm"],
        keep="last",
    )
    missing = dedupe_df.loc[missing_key_mask]
    out = pd.concat([non_missing, missing], axis=0)
    return out.drop(columns=["_pointid_norm", "_casing_top_norm", "_screen_top_norm"])


def _load_json_mapping(path: str) -> dict[str, str]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _ownersdata_agreed_filter(df: pd.DataFrame) -> pd.DataFrame:
    # Mirror ContactTransfer fan-out:
    # one OwnersData source row can produce 0/1/2 Contact rows.
    odf = df.drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")
    ldf = read_csv("OwnerLink").drop(["OBJECTID", "GlobalID"], axis=1, errors="ignore")
    locdf = read_csv("Location")
    ldf = ldf.join(locdf.set_index("LocationId"), on="LocationId")

    owner_key_col = _select_ownerkey_col(odf, "OwnersData")
    link_owner_key_col = _select_ownerkey_col(ldf, "OwnerLink")

    ownerkey_mapper = _load_json_mapping(
        str(get_transfers_data_path("owners_ownerkey_mapper.json"))
    )
    org_mapper = _load_json_mapping(
        str(get_transfers_data_path("owners_organization_mapper.json"))
    )

    if ownerkey_mapper:
        odf["ownerkey_canonical"] = odf[owner_key_col].replace(ownerkey_mapper)
        ldf["ownerkey_canonical"] = ldf[link_owner_key_col].replace(ownerkey_mapper)
    else:
        odf["ownerkey_canonical"] = odf[owner_key_col]
        ldf["ownerkey_canonical"] = ldf[link_owner_key_col]

    odf["ownerkey_norm"] = (
        odf["ownerkey_canonical"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )
    ldf["ownerkey_norm"] = (
        ldf["ownerkey_canonical"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .replace({"": pd.NA})
    )

    ldf_join = ldf.set_index("ownerkey_norm")
    overlap_cols = [col for col in ldf_join.columns if col in odf.columns]
    if overlap_cols:
        ldf_join = ldf_join.drop(columns=overlap_cols, errors="ignore")
    odf = odf.join(ldf_join, on="ownerkey_norm")

    odf = replace_nans(odf)
    odf = filter_to_valid_point_ids(odf)

    # Emulate ContactTransfer + _make_contact_and_assoc semantics:
    # 1) dedupe by (OwnerKey, ContactType)
    # 2) then dedupe by (name, organization) via in-memory "added" list
    # 3) only successful CreateContact payloads count as agreed.
    agreed_rows: list[dict[str, Any]] = []
    created_owner_type: set[tuple[str, str]] = set()
    added_name_org: set[tuple[str | None, str | None]] = set()

    ordered = odf.sort_values(by=["PointID"], kind="stable")

    def _record_new_contact(
        owner_key: Any,
        contact_type: str,
        name: str | None,
        organization: str | None,
    ) -> bool:
        if name is None and organization is None:
            return False

        owner_key_text = None if owner_key is None else str(owner_key)
        owner_type_key = None
        if owner_key_text:
            owner_type_key = (owner_key_text, contact_type)

        if owner_type_key and owner_type_key in created_owner_type:
            return False

        name_org_key = (name, organization)
        if name_org_key in added_name_org:
            return False

        if owner_type_key:
            created_owner_type.add(owner_type_key)
        added_name_org.add(name_org_key)
        agreed_rows.append({"OwnerKey": owner_key})
        return True

    for row in ordered.itertuples():
        owner_key = getattr(row, owner_key_col, None)
        organization = _get_organization(row, org_mapper)

        primary_name = _safe_make_name(
            getattr(row, "FirstName", None),
            getattr(row, "LastName", None),
            owner_key,
            organization,
            fallback_suffix="primary",
        )
        _record_new_contact(owner_key, "Primary", primary_name, organization)

        has_secondary_input = not all(
            [
                getattr(row, "SecondFirstName", None) is None,
                getattr(row, "SecondLastName", None) is None,
                getattr(row, "SecondCtctEmail", None) is None,
                getattr(row, "SecondCtctPhone", None) is None,
            ]
        )
        if has_secondary_input:
            secondary_name = _safe_make_name(
                getattr(row, "SecondFirstName", None),
                getattr(row, "SecondLastName", None),
                owner_key,
                organization,
                fallback_suffix="secondary",
            )
            _record_new_contact(owner_key, "Secondary", secondary_name, organization)

    return pd.DataFrame(agreed_rows, columns=["OwnerKey"])


TRANSFER_COMPARISON_SPECS: list[TransferComparisonSpec] = [
    TransferComparisonSpec(
        "WellData",
        WellDataTransferResult,
        "WellData",
        "WellID",
        Thing,
        "nma_pk_welldata",
        agreed_filter=_welldata_filter,
        destination_where=lambda m: m.thing_type == "water well",
    ),
    TransferComparisonSpec(
        "WellScreens",
        WellScreensTransferResult,
        "WellScreens",
        "GlobalID",
        WellScreen,
        "nma_pk_wellscreens",
        agreed_filter=_wellscreens_filter,
        option_field="transfer_screens",
    ),
    TransferComparisonSpec(
        "OwnersData",
        OwnersDataTransferResult,
        "OwnersData",
        "OwnerKey",
        Contact,
        "nma_pk_owners",
        agreed_filter=_ownersdata_agreed_filter,
        destination_where=lambda m: m.nma_pk_owners.is_not(None),
        option_field="transfer_contacts",
    ),
    TransferComparisonSpec(
        "Permissions",
        PermissionsTransferResult,
        "WellData",
        "PointID|PermissionType|PermissionAllowed",
        PermissionHistory,
        "thing.name|permission_type|permission_allowed",
        option_field="transfer_permissions",
    ),
    TransferComparisonSpec(
        "WaterLevels",
        WaterLevelsTransferResult,
        "WaterLevels",
        "GlobalID",
        Observation,
        "nma_pk_waterlevels",
        agreed_filter=_waterlevels_filter,
        option_field="transfer_waterlevels",
    ),
    TransferComparisonSpec(
        "Equipment",
        EquipmentTransferResult,
        "Equipment",
        "GlobalID",
        Sensor,
        "nma_pk_equipment",
        agreed_filter=_equipment_filter,
        option_field="transfer_sensors",
    ),
    TransferComparisonSpec(
        "Projects",
        ProjectsTransferResult,
        "Projects",
        "Project",
        Group,
        "name",
        option_field="transfer_groups",
    ),
    TransferComparisonSpec(
        "SurfaceWaterPhotos",
        SurfaceWaterPhotosTransferResult,
        "SurfaceWaterPhotos",
        "GlobalID",
        NMA_SurfaceWaterPhotos,
        "global_id",
        option_field="transfer_surface_water_photos",
    ),
    TransferComparisonSpec(
        "Soil_Rock_Results",
        SoilRockResultsTransferResult,
        "Soil_Rock_Results",
        "Point_ID",
        NMA_Soil_Rock_Results,
        "nma_point_id",
        option_field="transfer_soil_rock_results",
    ),
    TransferComparisonSpec(
        "WeatherPhotos",
        WeatherPhotosTransferResult,
        "WeatherPhotos",
        "GlobalID",
        NMA_WeatherPhotos,
        "global_id",
        option_field="transfer_weather_photos",
    ),
    TransferComparisonSpec(
        "AssociatedData",
        AssociatedDataTransferResult,
        "AssociatedData",
        "AssocID",
        NMA_AssociatedData,
        "nma_assoc_id",
        option_field="transfer_associated_data",
    ),
    TransferComparisonSpec(
        "SurfaceWaterData",
        SurfaceWaterDataTransferResult,
        "SurfaceWaterData",
        "OBJECTID",
        NMA_SurfaceWaterData,
        "object_id",
        option_field="transfer_surface_water_data",
    ),
    TransferComparisonSpec(
        "HydraulicsData",
        HydraulicsDataTransferResult,
        "HydraulicsData",
        "GlobalID",
        NMA_HydraulicsData,
        "nma_global_id",
        agreed_filter=_hydraulics_filter,
        option_field="transfer_hydraulics_data",
    ),
    TransferComparisonSpec(
        "Chemistry_SampleInfo",
        ChemistrySampleInfoTransferResult,
        "Chemistry_SampleInfo",
        "SamplePtID",
        NMA_Chemistry_SampleInfo,
        "nma_sample_pt_id",
        agreed_filter=_chemistry_sampleinfo_filter,
        option_field="transfer_chemistry_sampleinfo",
    ),
    TransferComparisonSpec(
        "view_NGWMN_WellConstruction",
        NGWMNWellConstructionTransferResult,
        "view_NGWMN_WellConstruction",
        "PointID",
        NMA_view_NGWMN_WellConstruction,
        "point_id",
        agreed_filter=_ngwmn_wellconstruction_filter,
        option_field="transfer_ngwmn_views",
    ),
    TransferComparisonSpec(
        "view_NGWMN_WaterLevels",
        NGWMNWaterLevelsTransferResult,
        "view_NGWMN_WaterLevels",
        "PointID",
        NMA_view_NGWMN_WaterLevels,
        "point_id",
        agreed_filter=_ngwmn_waterlevels_filter,
        option_field="transfer_ngwmn_views",
    ),
    TransferComparisonSpec(
        "view_NGWMN_Lithology",
        NGWMNLithologyTransferResult,
        "view_NGWMN_Lithology",
        "PointID",
        NMA_view_NGWMN_Lithology,
        "point_id",
        option_field="transfer_ngwmn_views",
    ),
    TransferComparisonSpec(
        "WaterLevelsContinuous_Pressure_Daily",
        PressureDailyTransferResult,
        "WaterLevelsContinuous_Pressure_Daily",
        "GlobalID",
        NMA_WaterLevelsContinuous_Pressure_Daily,
        "global_id",
        option_field="transfer_pressure_daily",
    ),
    TransferComparisonSpec(
        "WeatherData",
        WeatherDataTransferResult,
        "WeatherData",
        "OBJECTID",
        NMA_WeatherData,
        "object_id",
        option_field="transfer_weather_data",
    ),
    TransferComparisonSpec(
        "Stratigraphy",
        StratigraphyTransferResult,
        "Stratigraphy",
        "GlobalID",
        NMA_Stratigraphy,
        "nma_global_id",
        agreed_filter=_stratigraphy_filter,
        option_field="transfer_nma_stratigraphy",
    ),
    TransferComparisonSpec(
        "MajorChemistry",
        MajorChemistryTransferResult,
        "MajorChemistry",
        "GlobalID",
        NMA_MajorChemistry,
        "nma_global_id",
        agreed_filter=_chemistry_child_filter,
        option_field="transfer_major_chemistry",
    ),
    TransferComparisonSpec(
        "Radionuclides",
        RadionuclidesTransferResult,
        "Radionuclides",
        "GlobalID",
        NMA_Radionuclides,
        "nma_global_id",
        agreed_filter=_chemistry_child_filter,
        option_field="transfer_radionuclides",
    ),
    TransferComparisonSpec(
        "MinorandTraceChemistry",
        MinorTraceChemistryTransferResult,
        "MinorandTraceChemistry",
        "GlobalID",
        NMA_MinorTraceChemistry,
        "nma_global_id",
        agreed_filter=_chemistry_child_filter,
        option_field="transfer_minor_trace_chemistry",
    ),
    TransferComparisonSpec(
        "FieldParameters",
        FieldParametersTransferResult,
        "FieldParameters",
        "GlobalID",
        NMA_FieldParameters,
        "nma_global_id",
        agreed_filter=_chemistry_child_filter,
        option_field="transfer_field_parameters",
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
        option_field="transfer_springs",
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
        option_field="transfer_perennial_streams",
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
        option_field="transfer_ephemeral_streams",
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
        option_field="transfer_met_stations",
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
        option_field="transfer_rock_sample_locations",
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
        option_field="transfer_diversion_of_surface_water",
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
        option_field="transfer_lake_pond_reservoir",
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
        option_field="transfer_soil_gas_sample_locations",
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
        option_field="transfer_other_site_types",
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
        option_field="transfer_outfall_wastewater_return_flow",
    ),
]
