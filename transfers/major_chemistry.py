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

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import ChemistrySampleInfo, NMAMajorChemistry
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class MajorChemistryTransferer(Transferer):
    """
    Transfer for the legacy MajorChemistry table.
    """

    source_table = "MajorChemistry"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._sample_pt_ids: set[UUID] = set()
        self._build_sample_pt_id_cache()

    def _build_sample_pt_id_cache(self) -> None:
        with session_ctx() as session:
            sample_infos = session.query(ChemistrySampleInfo.sample_pt_id).all()
            self._sample_pt_ids = {sample_pt_id for (sample_pt_id,) in sample_infos}
        logger.info(
            f"Built ChemistrySampleInfo cache with {len(self._sample_pt_ids)} entries"
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table, parse_dates=["AnalysisDate"])
        cleaned_df = self._filter_to_valid_sample_infos(input_df)
        return input_df, cleaned_df

    def _filter_to_valid_sample_infos(self, df: pd.DataFrame) -> pd.DataFrame:
        valid_sample_pt_ids = self._sample_pt_ids
        mask = df["SamplePtID"].apply(
            lambda value: self._uuid_val(value) in valid_sample_pt_ids
        )
        before_count = len(df)
        filtered_df = df[mask].copy()
        after_count = len(filtered_df)

        if before_count > after_count:
            skipped = before_count - after_count
            logger.warning(
                f"Filtered out {skipped} MajorChemistry records without matching "
                f"ChemistrySampleInfo ({after_count} valid, {skipped} orphan records prevented)"
            )

        return filtered_df

    def _transfer_hook(self, session: Session) -> None:
        row_dicts = []
        skipped_global_id = 0
        for row in self.cleaned_df.to_dict("records"):
            row_dict = self._row_dict(row)
            if row_dict is None:
                continue
            if row_dict.get("GlobalID") is None:
                skipped_global_id += 1
                logger.warning(
                    "Skipping MajorChemistry SamplePtID=%s - GlobalID missing or invalid",
                    row_dict.get("SamplePtID"),
                )
                continue
            row_dicts.append(row_dict)

        if skipped_global_id > 0:
            logger.warning(
                "Skipped %s MajorChemistry records without valid GlobalID",
                skipped_global_id,
            )

        rows = self._dedupe_rows(row_dicts, key="GlobalID")
        insert_stmt = insert(NMAMajorChemistry)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into MajorChemistry"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "SamplePtID": excluded.SamplePtID,
                    "SamplePointID": excluded.SamplePointID,
                    "Analyte": excluded.Analyte,
                    "Symbol": excluded.Symbol,
                    "SampleValue": excluded.SampleValue,
                    "Units": excluded.Units,
                    "Uncertainty": excluded.Uncertainty,
                    "AnalysisMethod": excluded.AnalysisMethod,
                    "AnalysisDate": excluded.AnalysisDate,
                    "Notes": excluded.Notes,
                    "Volume": excluded.Volume,
                    "VolumeUnit": excluded.VolumeUnit,
                    "OBJECTID": excluded.OBJECTID,
                    "AnalysesAgency": excluded.AnalysesAgency,
                    "WCLab_ID": excluded.WCLab_ID,
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_dict(self, row: dict[str, Any]) -> Optional[dict[str, Any]]:
        def val(key: str) -> Optional[Any]:
            v = row.get(key)
            if pd.isna(v):
                return None
            return v

        def float_val(key: str) -> Optional[float]:
            v = val(key)
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def int_val(key: str) -> Optional[int]:
            v = val(key)
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        analysis_date = val("AnalysisDate")
        if hasattr(analysis_date, "to_pydatetime"):
            analysis_date = analysis_date.to_pydatetime()
        if isinstance(analysis_date, datetime):
            analysis_date = analysis_date.replace(tzinfo=None)

        sample_pt_id = self._uuid_val(val("SamplePtID"))
        if sample_pt_id is None:
            self._capture_error(
                val("SamplePtID"),
                f"Invalid SamplePtID: {val('SamplePtID')}",
                "SamplePtID",
            )
            return None

        global_id = self._uuid_val(val("GlobalID"))

        return {
            "SamplePtID": sample_pt_id,
            "SamplePointID": val("SamplePointID"),
            "Analyte": val("Analyte"),
            "Symbol": val("Symbol"),
            "SampleValue": float_val("SampleValue"),
            "Units": val("Units"),
            "Uncertainty": float_val("Uncertainty"),
            "AnalysisMethod": val("AnalysisMethod"),
            "AnalysisDate": analysis_date,
            "Notes": val("Notes"),
            "Volume": int_val("Volume"),
            "VolumeUnit": val("VolumeUnit"),
            "OBJECTID": val("OBJECTID"),
            "GlobalID": global_id,
            "AnalysesAgency": val("AnalysesAgency"),
            "WCLab_ID": val("WCLab_ID"),
        }

    def _dedupe_rows(
        self, rows: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """Dedupe rows by unique key to avoid ON CONFLICT loops. Later rows win."""
        deduped = {}
        for row in rows:
            gid = row.get(key)
            if gid is None:
                continue
            deduped[gid] = row
        return list(deduped.values())

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


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = MajorChemistryTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.major_chemistry`
    run()

# ============= EOF =============================================
