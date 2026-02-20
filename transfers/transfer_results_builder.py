from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, func

from db.engine import session_ctx
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
    read_csv,
    replace_nans,
    get_transferable_wells,
)


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

        source_series = _normalized_series(comparison_df, spec.source_key_column)
        source_keys = set(source_series.unique().tolist())
        source_keyed_row_count = int(source_series.shape[0])
        source_duplicate_key_row_count = source_keyed_row_count - len(source_keys)
        agreed_transfer_row_count = int(len(comparison_df))

        model = spec.destination_model
        key_col = getattr(model, spec.destination_key_column)
        with session_ctx() as session:
            key_sql = select(key_col).where(key_col.is_not(None))
            count_sql = select(func.count()).select_from(model)

            if spec.destination_where:
                where_clause = spec.destination_where(model)
                key_sql = key_sql.where(where_clause)
                count_sql = count_sql.where(where_clause)

            raw_dest_keys = session.execute(key_sql).scalars().all()
            destination_row_count = int(session.execute(count_sql).scalar_one())

        destination_series = pd.Series(
            [_normalize_key(v) for v in raw_dest_keys], dtype=object
        ).dropna()
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

        return spec.result_cls(
            transfer_name=spec.transfer_name,
            source_csv=spec.source_csv,
            source_key_column=spec.source_key_column,
            destination_model=model.__name__,
            destination_key_column=spec.destination_key_column,
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
