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
"""Transfer FieldParameters data from NM_Aquifer to NMA_FieldParameters.

This transfer requires ChemistrySampleInfo to be backfilled first. Each
FieldParameters record links to a ChemistrySampleInfo record via SamplePtID.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import NMA_Chemistry_SampleInfo, NMA_FieldParameters
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class FieldParametersTransferer(Transferer):
    """
    Transfer FieldParameters records to NMA_FieldParameters.

    Looks up ChemistrySampleInfo by SamplePtID and creates linked
    FieldParameters records. Uses upsert for idempotent transfers.
    """

    source_table = "FieldParameters"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._sample_pt_ids: set[UUID] = set()
        self._build_sample_pt_id_cache()

    def _build_sample_pt_id_cache(self) -> None:
        """Build cache of ChemistrySampleInfo.SamplePtID values."""
        with session_ctx() as session:
            sample_infos = session.query(NMA_Chemistry_SampleInfo.sample_pt_id).all()
            self._sample_pt_ids = {sample_pt_id for (sample_pt_id,) in sample_infos}
        logger.info(
            f"Built ChemistrySampleInfo cache with {len(self._sample_pt_ids)} entries"
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table)
        cleaned_df = self._filter_to_valid_sample_infos(input_df)
        return input_df, cleaned_df

    def _filter_to_valid_sample_infos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to only include rows where SamplePtID matches a ChemistrySampleInfo.

        This prevents orphan records and ensures the FK constraint will be satisfied.
        """
        valid_sample_pt_ids = self._sample_pt_ids
        before_count = len(df)
        mask = df["SamplePtID"].apply(
            lambda value: self._uuid_val(value) in valid_sample_pt_ids
        )
        filtered_df = df[mask].copy()
        after_count = len(filtered_df)

        if before_count > after_count:
            skipped = before_count - after_count
            logger.warning(
                f"Filtered out {skipped} FieldParameters records without matching "
                f"ChemistrySampleInfo ({after_count} valid, {skipped} orphan records prevented)"
            )

        return filtered_df

    def _transfer_hook(self, session: Session) -> None:
        """
        Override transfer hook to use batch upsert for idempotent transfers.

        Uses ON CONFLICT DO UPDATE on GlobalID.
        """
        limit = self.flags.get("LIMIT", 0)
        df = self.cleaned_df
        if limit > 0:
            df = df.head(limit)

        row_dicts = []
        for row in df.itertuples():
            row_dict = self._row_to_dict(row)
            if row_dict is not None:
                row_dicts.append(row_dict)

        if not row_dicts:
            logger.warning("No valid rows to transfer")
            return

        rows = self._dedupe_rows(row_dicts)
        logger.info(f"Upserting {len(rows)} FieldParameters records")

        insert_stmt = insert(NMA_FieldParameters)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows)")
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "SamplePtID": excluded.SamplePtID,
                    "SamplePointID": excluded.SamplePointID,
                    "FieldParameter": excluded.FieldParameter,
                    "SampleValue": excluded.SampleValue,
                    "Units": excluded.Units,
                    "Notes": excluded.Notes,
                    "OBJECTID": excluded.OBJECTID,
                    "AnalysesAgency": excluded.AnalysesAgency,
                    "WCLab_ID": excluded.WCLab_ID,
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_to_dict(self, row) -> Optional[dict[str, Any]]:
        """Convert a DataFrame row to a dict for upsert."""
        sample_pt_id = self._uuid_val(getattr(row, "SamplePtID", None))
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

        global_id = self._uuid_val(getattr(row, "GlobalID", None))
        if global_id is None:
            self._capture_error(
                getattr(row, "GlobalID", None),
                f"Invalid GlobalID: {getattr(row, 'GlobalID', None)}",
                "GlobalID",
            )
            return None

        return {
            "GlobalID": global_id,
            "SamplePtID": sample_pt_id,
            "SamplePointID": self._safe_str(row, "SamplePointID"),
            "FieldParameter": self._safe_str(row, "FieldParameter"),
            "SampleValue": self._safe_float(row, "SampleValue"),
            "Units": self._safe_str(row, "Units"),
            "Notes": self._safe_str(row, "Notes"),
            "OBJECTID": self._safe_int(row, "OBJECTID"),
            "AnalysesAgency": self._safe_str(row, "AnalysesAgency"),
            "WCLab_ID": self._safe_str(row, "WCLab_ID"),
        }

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Dedupe rows by unique key to avoid ON CONFLICT loops. Later rows win."""
        deduped = {}
        for row in rows:
            key = row.get("GlobalID")
            if key is None:
                continue
            deduped[key] = row
        return list(deduped.values())

    def _safe_str(self, row, attr: str) -> Optional[str]:
        """Safely get a string value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        return str(val)

    def _safe_float(self, row, attr: str) -> Optional[float]:
        """Safely get a float value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, row, attr: str) -> Optional[int]:
        """Safely get an int value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

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


def run(flags: dict = None) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Entrypoint to execute the transfer."""
    transferer = FieldParametersTransferer(flags=flags)
    transferer.transfer()
    return transferer.input_df, transferer.cleaned_df, transferer.errors


if __name__ == "__main__":
    # Allow running via `python -m transfers.field_parameters_transfer`
    run()

# ============= EOF =============================================
