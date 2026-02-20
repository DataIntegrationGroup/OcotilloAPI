from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, func

from db.engine import session_ctx
from transfers.transfer_results_specs import (
    TRANSFER_COMPARISON_SPECS,
    TransferComparisonSpec,
)
from transfers.transfer_results_types import (
    TransferComparisonResults,
    TransferResult,
)
from transfers.util import read_csv


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
        source_series = _normalized_series(source_df, spec.source_key_column)
        source_keys = set(source_series.unique().tolist())
        source_keyed_row_count = int(source_series.shape[0])
        source_duplicate_key_row_count = source_keyed_row_count - len(source_keys)
        agreed_transfer_row_count = int(len(source_df))
        if spec.agreed_row_counter is not None:
            try:
                agreed_transfer_row_count = int(spec.agreed_row_counter())
            except Exception:
                agreed_transfer_row_count = int(len(source_df))

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

    @staticmethod
    def write_summary(path: Path, comparison: TransferComparisonResults) -> None:
        lines = [
            f"generated_at={comparison.generated_at}",
            "",
            "| Transfer | Source CSV | Source Rows | Agreed Rows | Dest Model | Dest Rows | Missing Agreed | Matched | Missing | Extra |",
            "|---|---|---:|---:|---|---:|---:|---:|---:|---:|",
        ]
        for name in sorted(comparison.results.keys()):
            r = comparison.results[name]
            missing_agreed = r.agreed_transfer_row_count - r.destination_row_count
            lines.append(
                f"| {name} | {r.source_csv} | {r.source_row_count} | {r.agreed_transfer_row_count} | "
                f"{r.destination_model} | {r.destination_row_count} | {missing_agreed} | "
                f"{r.matched_key_count} | {r.missing_in_destination_count} | {r.extra_in_destination_count} |"
            )
        path.write_text("\n".join(lines) + "\n")
