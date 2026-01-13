# ===============================================================================
# Copyright 2026 ross
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
"""
Transfer MinorandTraceChemistry data from NM_Aquifer to NMAMinorTraceChemistry.

This transfer requires ChemistrySampleInfo to be backfilled first (which links
to Thing via thing_id). Each MinorTraceChemistry record links to a ChemistrySampleInfo
record via chemistry_sample_info_id.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import ChemistrySampleInfo, NMAMinorTraceChemistry
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class MinorTraceChemistryTransferer(Transferer):
    """
    Transfer MinorandTraceChemistry records to NMAMinorTraceChemistry.

    Looks up ChemistrySampleInfo by SamplePtID and creates linked
    NMAMinorTraceChemistry records. Uses upsert for idempotent transfers.
    """

    source_table = "MinorandTraceChemistry"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        # Cache ChemistrySampleInfo SamplePtIDs for FK validation
        self._sample_pt_ids: set[UUID] = set()
        self._build_sample_pt_id_cache()

    def _build_sample_pt_id_cache(self):
        """Build cache of ChemistrySampleInfo.SamplePtID values."""
        with session_ctx() as session:
            sample_infos = session.query(ChemistrySampleInfo.sample_pt_id).all()
            self._sample_pt_ids = {sample_pt_id for (sample_pt_id,) in sample_infos}
        logger.info(
            f"Built ChemistrySampleInfo cache with {len(self._sample_pt_ids)} entries"
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table)
        # Filter to only include rows where ChemistrySampleInfo exists
        cleaned_df = self._filter_to_valid_sample_infos(input_df)
        return input_df, cleaned_df

    def _filter_to_valid_sample_infos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to only include rows where SamplePtID matches a ChemistrySampleInfo.

        This prevents orphan records and ensures the FK constraint will be satisfied.
        """
        valid_sample_pt_ids = self._sample_pt_ids

        before_count = len(df)
        df = df.copy()
        df["_sample_pt_uuid"] = df["SamplePtID"].apply(self._uuid_val)
        filtered_df = df[df["_sample_pt_uuid"].isin(valid_sample_pt_ids)].copy()
        filtered_df.drop(columns=["_sample_pt_uuid"], inplace=True)
        after_count = len(filtered_df)

        if before_count > after_count:
            skipped = before_count - after_count
            logger.warning(
                f"Filtered out {skipped} MinorTraceChemistry records without matching "
                f"ChemistrySampleInfo ({after_count} valid, {skipped} orphan records prevented)"
            )

        return filtered_df

    def _transfer_hook(self, session: Session) -> None:
        """
        Override transfer hook to use batch upsert for idempotent transfers.

        Uses ON CONFLICT DO UPDATE on (chemistry_sample_info_id, analyte).
        """
        limit = self.flags.get("LIMIT", 0)
        df = self.cleaned_df
        if limit > 0:
            df = df.head(limit)

        # Convert rows to dicts
        row_dicts = []
        for row in df.itertuples():
            row_dict = self._row_to_dict(row)
            if row_dict is not None:
                row_dicts.append(row_dict)

        if not row_dicts:
            logger.warning("No valid rows to transfer")
            return

        # Dedupe by unique key (chemistry_sample_info_id, analyte)
        rows = self._dedupe_rows(row_dicts)
        logger.info(f"Upserting {len(rows)} MinorTraceChemistry records")

        insert_stmt = insert(NMAMinorTraceChemistry)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows)")
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                constraint="uq_minor_trace_chemistry_sample_analyte",
                set_={
                    "sample_value": excluded.sample_value,
                    "units": excluded.units,
                    "symbol": excluded.symbol,
                    "analysis_method": excluded.analysis_method,
                    "analysis_date": excluded.analysis_date,
                    "notes": excluded.notes,
                    "analyses_agency": excluded.analyses_agency,
                    "uncertainty": excluded.uncertainty,
                    "volume": excluded.volume,
                    "volume_unit": excluded.volume_unit,
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_to_dict(self, row) -> Optional[dict[str, Any]]:
        """Convert a DataFrame row to a dict for upsert."""
        sample_pt_id = self._uuid_val(row.SamplePtID)
        if sample_pt_id is None:
            self._capture_error(
                getattr(row, "SamplePtID", None),
                f"Invalid SamplePtID: {getattr(row, 'SamplePtID', None)}",
                "SamplePtID",
            )
            return None

        if sample_pt_id not in self._sample_pt_ids:
            self._capture_error(
                sample_pt_id,
                f"ChemistrySampleInfo not found for SamplePtID: {sample_pt_id}",
                "SamplePtID",
            )
            return None

        return {
            "chemistry_sample_info_id": sample_pt_id,
            "analyte": self._safe_str(row, "Analyte"),
            "sample_value": self._safe_float(row, "SampleValue"),
            "units": self._safe_str(row, "Units"),
            "symbol": self._safe_str(row, "Symbol"),
            "analysis_method": self._safe_str(row, "AnalysisMethod"),
            "analysis_date": self._parse_date(row, "AnalysisDate"),
            "notes": self._safe_str(row, "Notes"),
            "analyses_agency": self._safe_str(row, "AnalysesAgency"),
            "uncertainty": self._safe_float(row, "Uncertainty"),
            "volume": self._safe_float(row, "Volume"),
            "volume_unit": self._safe_str(row, "VolumeUnit"),
        }

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Dedupe rows by unique key to avoid ON CONFLICT loops. Later rows win."""
        deduped = {}
        for row in rows:
            key = (row["chemistry_sample_info_id"], row["analyte"])
            deduped[key] = row
        return list(deduped.values())

    def _safe_str(self, row, attr: str) -> Optional[str]:
        """Safely get a string value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        return str(val)

    def _uuid_val(self, value: Any) -> Optional[UUID]:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                return None
        return None

    def _safe_float(self, row, attr: str) -> Optional[float]:
        """Safely get a float value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        return float(val)

    def _parse_date(self, row, attr: str) -> Optional[date]:
        """Parse a date value from the row."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None

        # Handle pandas Timestamp
        if hasattr(val, "date"):
            return val.date()

        # Handle string dates
        if isinstance(val, str):
            try:
                # Try common date formats (most specific first)
                for fmt in [
                    "%Y-%m-%d %H:%M:%S.%f",  # With milliseconds/microseconds
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%m/%d/%Y",
                ]:
                    try:
                        return datetime.strptime(val, fmt).date()
                    except ValueError:
                        continue
                logger.warning(f"Could not parse date: {val}")
                return None
            except Exception as e:
                logger.warning(f"Error parsing date {val}: {e}")
                return None

        return None


def run(flags: dict = None) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Entrypoint to execute the transfer."""
    transferer = MinorTraceChemistryTransferer(flags=flags)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


if __name__ == "__main__":
    # Allow running via `python -m transfers.minor_trace_chemistry_transfer`
    run()

# ============= EOF =============================================
