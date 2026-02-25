from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, func

from db import Deployment, PermissionHistory, Sensor, Thing, ThingContactAssociation
from db.engine import session_ctx
from transfers.sensor_transfer import (
    EQUIPMENT_TO_SENSOR_TYPE_MAP,
)
from transfers.transfer import load_transfer_options
from transfers.transfer_results_specs import (
    TRANSFER_COMPARISON_SPECS,
    TransferComparisonSpec,
)
from transfers.transfer_results_types import (
    TransferComparisonResults,
    TransferResult,
)
from transfers.util import (
    SensorParameterEstimator,
    read_csv,
    replace_nans,
    get_transferable_wells,
)


def _model_column(model: Any, token: str) -> Any:
    if hasattr(model, token):
        return getattr(model, token)
    table = model.__table__
    if token in table.c:
        return table.c[token]
    token_norm = token.casefold()
    for col in table.c:
        if col.key.casefold() == token_norm or col.name.casefold() == token_norm:
            return col
    raise AttributeError(f"{model.__name__} has no column '{token}'")


def _normalize_key(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    s = str(value).strip()
    if not s:
        return None
    return s.lower()


def _source_keys(df: pd.DataFrame, key_col: str) -> set[str]:
    if key_col not in df.columns:
        return set()
    return {
        key
        for key in (_normalize_key(v) for v in df[key_col].tolist())
        if key is not None
    }


def _normalized_series(df: pd.DataFrame, key_col: str) -> pd.Series:
    if key_col not in df.columns:
        return pd.Series([], dtype=object)
    s = df[key_col].map(_normalize_key).dropna()
    if s.empty:
        return pd.Series([], dtype=object)
    return s.astype(str)


def _normalize_date_like(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.date().isoformat()


def _parse_legacy_datetime_date(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value).strip()
    if not text:
        return None
    try:
        return pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S.%f").date().isoformat()
    except (TypeError, ValueError):
        return None


def _equipment_source_series(df: pd.DataFrame) -> pd.Series:
    required = {"PointID", "SerialNo", "DateInstalled", "DateRemoved"}
    if not required.issubset(df.columns):
        return pd.Series([], dtype=object)

    estimators: dict[str, SensorParameterEstimator] = {}
    keys: list[str] = []
    for row in df.itertuples(index=False):
        pointid = _normalize_key(getattr(row, "PointID", None)) or ""
        serial = _normalize_key(getattr(row, "SerialNo", None)) or ""

        installed = _parse_legacy_datetime_date(getattr(row, "DateInstalled", None))
        if installed is None:
            equipment_type = getattr(row, "EquipmentType", None)
            sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP.get(equipment_type)
            if sensor_type:
                estimator = estimators.get(sensor_type)
                if estimator is None:
                    estimator = SensorParameterEstimator(sensor_type)
                    estimators[sensor_type] = estimator
                estimated = estimator.estimate_installation_date(row)
                installed = _normalize_date_like(estimated)
            else:
                installed = ""

        removed = _parse_legacy_datetime_date(getattr(row, "DateRemoved", None))
        if removed is None:
            removed = ""

        keys.append(f"{pointid}|{serial}|{installed}|{removed}")
    return pd.Series(keys, dtype=object)


def _equipment_destination_series(session) -> pd.Series:
    sql = (
        select(
            Thing.name.label("point_id"),
            Sensor.serial_no.label("serial_no"),
            Deployment.installation_date.label("installed"),
            Deployment.removal_date.label("removed"),
        )
        .select_from(Deployment)
        .join(Thing, Deployment.thing_id == Thing.id)
        .join(Sensor, Deployment.sensor_id == Sensor.id)
        .where(Thing.name.is_not(None))
        .where(Sensor.serial_no.is_not(None))
    )
    rows = session.execute(sql).all()
    if not rows:
        return pd.Series([], dtype=object)
    pointid = pd.Series([_normalize_key(r.point_id) or "" for r in rows], dtype=object)
    serial = pd.Series([_normalize_key(r.serial_no) or "" for r in rows], dtype=object)
    installed = pd.Series(
        [_normalize_date_like(r.installed) for r in rows], dtype=object
    )
    removed = pd.Series([_normalize_date_like(r.removed) for r in rows], dtype=object)
    return pointid + "|" + serial + "|" + installed + "|" + removed


def _permissions_source_series(session) -> pd.Series:
    wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
    wdf = replace_nans(wdf)
    if "PointID" not in wdf.columns:
        return pd.Series([], dtype=object)

    eligible_rows = (
        session.query(Thing.name)
        .join(ThingContactAssociation, ThingContactAssociation.thing_id == Thing.id)
        .filter(Thing.thing_type == "water well")
        .filter(Thing.name.is_not(None))
        .distinct()
        .all()
    )
    eligible_pointids = {name for (name,) in eligible_rows if name}
    if not eligible_pointids:
        return pd.Series([], dtype=object)

    rows: list[str] = []
    for row in wdf.itertuples(index=False):
        pointid = getattr(row, "PointID", None)
        if pointid not in eligible_pointids:
            continue

        sample_ok = getattr(row, "SampleOK", None)
        if sample_ok is not None:
            rows.append(
                f"{_normalize_key(pointid)}|Water Chemistry Sample|{bool(sample_ok)}"
            )

        monitor_ok = getattr(row, "MonitorOK", None)
        if monitor_ok is not None:
            rows.append(
                f"{_normalize_key(pointid)}|Water Level Sample|{bool(monitor_ok)}"
            )

    if not rows:
        return pd.Series([], dtype=object)
    return pd.Series(rows, dtype=object)


def _permissions_destination_series(session) -> pd.Series:
    sql = (
        select(
            Thing.name.label("point_id"),
            PermissionHistory.permission_type.label("permission_type"),
            PermissionHistory.permission_allowed.label("permission_allowed"),
        )
        .select_from(PermissionHistory)
        .join(Thing, Thing.id == PermissionHistory.target_id)
        .where(PermissionHistory.target_table == "thing")
        .where(
            PermissionHistory.permission_type.in_(
                ("Water Chemistry Sample", "Water Level Sample")
            )
        )
        .where(Thing.name.is_not(None))
    )
    rows = session.execute(sql).all()
    if not rows:
        return pd.Series([], dtype=object)
    return pd.Series(
        [
            f"{_normalize_key(r.point_id)}|{r.permission_type}|{bool(r.permission_allowed)}"
            for r in rows
        ],
        dtype=object,
    )


class TransferResultsBuilder:
    """Compare transfer input CSV keys to destination database keys per transfer."""

    def __init__(self, sample_limit: int = 25):
        self.sample_limit = sample_limit
        self.transfer_options = load_transfer_options()
        self.transfer_limit = int(os.getenv("TRANSFER_LIMIT", "1000"))

    def build(self) -> TransferComparisonResults:
        results: dict[str, TransferResult] = {}
        for spec in TRANSFER_COMPARISON_SPECS:
            results[spec.transfer_name] = self._build_one(spec)
        return TransferComparisonResults(
            generated_at=pd.Timestamp.utcnow().isoformat(),
            results=results,
        )

    def _build_one(self, spec: TransferComparisonSpec) -> TransferResult:
        if spec.transfer_name == "Permissions":
            return self._build_permissions(spec)

        source_df = read_csv(spec.source_csv)
        if spec.source_filter:
            source_df = spec.source_filter(source_df)
        comparison_df = source_df
        if spec.agreed_filter:
            comparison_df = spec.agreed_filter(comparison_df)
        enabled = self._is_enabled(spec)
        if not enabled:
            comparison_df = comparison_df.iloc[0:0]
        elif spec.transfer_name == "WellData":
            comparison_df = self._agreed_welldata_df()

        if spec.transfer_name == "Equipment":
            source_series = _equipment_source_series(comparison_df)
        else:
            source_series = _normalized_series(comparison_df, spec.source_key_column)
        source_keys = set(source_series.unique().tolist())
        source_keyed_row_count = int(source_series.shape[0])
        source_duplicate_key_row_count = source_keyed_row_count - len(source_keys)
        agreed_transfer_row_count = int(len(comparison_df))

        model = spec.destination_model
        destination_model_name = model.__name__
        destination_key_column = spec.destination_key_column
        with session_ctx() as session:
            if spec.transfer_name == "Equipment":
                count_sql = select(func.count()).select_from(Deployment)
                count_sql = count_sql.join(Thing, Deployment.thing_id == Thing.id)
                count_sql = count_sql.join(Sensor, Deployment.sensor_id == Sensor.id)
                count_sql = count_sql.where(Thing.name.is_not(None))
                count_sql = count_sql.where(Sensor.serial_no.is_not(None))
                destination_series = _equipment_destination_series(session)
                destination_row_count = int(session.execute(count_sql).scalar_one())
                destination_model_name = "Deployment"
                destination_key_column = "thing.name|sensor.serial_no|deployment.installation_date|deployment.removal_date"
            else:
                key_col = _model_column(model, spec.destination_key_column)
                key_sql = select(key_col).where(key_col.is_not(None))
                count_sql = select(func.count()).select_from(model)

                if spec.destination_where:
                    where_clause = spec.destination_where(model)
                    key_sql = key_sql.where(where_clause)
                    count_sql = count_sql.where(where_clause)

                raw_dest_keys = session.execute(key_sql).scalars().all()
                destination_series = pd.Series(
                    [_normalize_key(v) for v in raw_dest_keys], dtype=object
                ).dropna()
                destination_row_count = int(session.execute(count_sql).scalar_one())

        if destination_series.empty:
            destination_series = pd.Series([], dtype=object)
        else:
            destination_series = destination_series.astype(str)

        destination_keys = set(destination_series.unique().tolist())
        destination_keyed_row_count = int(destination_series.shape[0])
        destination_duplicate_key_row_count = destination_keyed_row_count - len(
            destination_keys
        )

        missing = sorted(source_keys - destination_keys)
        extra = sorted(destination_keys - source_keys)
        transferred_agreed_row_count = int(source_series.isin(destination_keys).sum())
        missing_agreed_row_count = max(
            agreed_transfer_row_count - transferred_agreed_row_count,
            0,
        )

        return spec.result_cls(
            transfer_name=spec.transfer_name,
            source_csv=spec.source_csv,
            source_key_column=spec.source_key_column,
            destination_model=destination_model_name,
            destination_key_column=destination_key_column,
            source_row_count=len(source_df),
            agreed_transfer_row_count=agreed_transfer_row_count,
            source_keyed_row_count=source_keyed_row_count,
            source_key_count=len(source_keys),
            source_duplicate_key_row_count=source_duplicate_key_row_count,
            destination_row_count=destination_row_count,
            destination_keyed_row_count=destination_keyed_row_count,
            destination_key_count=len(destination_keys),
            destination_duplicate_key_row_count=destination_duplicate_key_row_count,
            matched_key_count=len(source_keys & destination_keys),
            missing_in_destination_count=len(missing),
            extra_in_destination_count=len(extra),
            transferred_agreed_row_count=transferred_agreed_row_count,
            missing_agreed_row_count=missing_agreed_row_count,
            missing_in_destination_sample=missing[: self.sample_limit],
            extra_in_destination_sample=extra[: self.sample_limit],
        )

    def _build_permissions(self, spec: TransferComparisonSpec) -> TransferResult:
        source_df = read_csv(spec.source_csv, dtype={"OSEWelltagID": str})
        source_row_count = len(source_df)
        enabled = self._is_enabled(spec)

        with session_ctx() as session:
            source_series = (
                _permissions_source_series(session)
                if enabled
                else pd.Series([], dtype=object)
            )
            source_keys = set(source_series.unique().tolist())
            source_keyed_row_count = int(source_series.shape[0])
            source_duplicate_key_row_count = source_keyed_row_count - len(source_keys)
            agreed_transfer_row_count = source_keyed_row_count

            destination_series = _permissions_destination_series(session)
            destination_row_count = int(
                session.execute(
                    select(func.count())
                    .select_from(PermissionHistory)
                    .where(PermissionHistory.target_table == "thing")
                    .where(
                        PermissionHistory.permission_type.in_(
                            ("Water Chemistry Sample", "Water Level Sample")
                        )
                    )
                ).scalar_one()
            )

        if destination_series.empty:
            destination_series = pd.Series([], dtype=object)
        else:
            destination_series = destination_series.astype(str)

        destination_keys = set(destination_series.unique().tolist())
        destination_keyed_row_count = int(destination_series.shape[0])
        destination_duplicate_key_row_count = destination_keyed_row_count - len(
            destination_keys
        )
        missing = sorted(source_keys - destination_keys)
        extra = sorted(destination_keys - source_keys)
        transferred_agreed_row_count = int(source_series.isin(destination_keys).sum())
        missing_agreed_row_count = max(
            agreed_transfer_row_count - transferred_agreed_row_count,
            0,
        )

        return spec.result_cls(
            transfer_name=spec.transfer_name,
            source_csv=spec.source_csv,
            source_key_column=spec.source_key_column,
            destination_model="PermissionHistory",
            destination_key_column=spec.destination_key_column,
            source_row_count=source_row_count,
            agreed_transfer_row_count=agreed_transfer_row_count,
            source_keyed_row_count=source_keyed_row_count,
            source_key_count=len(source_keys),
            source_duplicate_key_row_count=source_duplicate_key_row_count,
            destination_row_count=destination_row_count,
            destination_keyed_row_count=destination_keyed_row_count,
            destination_key_count=len(destination_keys),
            destination_duplicate_key_row_count=destination_duplicate_key_row_count,
            matched_key_count=len(source_keys & destination_keys),
            missing_in_destination_count=len(missing),
            extra_in_destination_count=len(extra),
            transferred_agreed_row_count=transferred_agreed_row_count,
            missing_agreed_row_count=missing_agreed_row_count,
            missing_in_destination_sample=missing[: self.sample_limit],
            extra_in_destination_sample=extra[: self.sample_limit],
        )

    def _is_enabled(self, spec: TransferComparisonSpec) -> bool:
        if not spec.option_field:
            return True
        return bool(getattr(self.transfer_options, spec.option_field, True))

    def _agreed_welldata_df(self) -> pd.DataFrame:
        wdf = read_csv("WellData", dtype={"OSEWelltagID": str})
        ldf = read_csv("Location")
        ldf = ldf.drop(["PointID", "SSMA_TimeStamp"], axis=1, errors="ignore")
        wdf = wdf.join(ldf.set_index("LocationId"), on="LocationId")
        wdf = wdf[wdf["SiteType"] == "GW"]
        wdf = wdf[wdf["Easting"].notna() & wdf["Northing"].notna()]
        wdf = replace_nans(wdf)

        cleaned_df = get_transferable_wells(wdf)

        dupes = cleaned_df["PointID"].duplicated(keep=False)
        if dupes.any():
            dup_ids = set(cleaned_df.loc[dupes, "PointID"])
            cleaned_df = cleaned_df[~cleaned_df["PointID"].isin(dup_ids)]

        if self.transfer_limit > 0:
            cleaned_df = cleaned_df.head(self.transfer_limit)
        return cleaned_df

    @staticmethod
    def write_summary(path: Path, comparison: TransferComparisonResults) -> None:
        lines = [
            f"generated_at={comparison.generated_at}",
            "",
            "| Transfer | Source CSV | Source Rows | Agreed Rows | Dest Model | Dest Rows | Missing Agreed |",
            "|---|---|---:|---:|---|---:|---:|",
        ]
        for name in sorted(comparison.results.keys()):
            r = comparison.results[name]
            lines.append(
                f"| {name} | {r.source_csv} | {r.source_row_count} | {r.agreed_transfer_row_count} | "
                f"{r.destination_model} | {r.destination_row_count} | {r.missing_in_destination_count} |"
            )
        path.write_text("\n".join(lines) + "\n")
