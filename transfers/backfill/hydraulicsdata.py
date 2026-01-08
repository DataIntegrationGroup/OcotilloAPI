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

from typing import Any, Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import NMAHydraulicsData
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class NMAHydraulicsDataBackfill(Transferer):
    """
    Backfill for the legacy NMA_HydraulicsData table.
    """

    source_table = "HydraulicsData"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table)
        return input_df, input_df

    def _transfer_hook(self, session: Session) -> None:
        rows = self._dedupe_rows(
            [self._row_dict(row) for row in self.cleaned_df.to_dict("records")],
            key="GlobalID",
        )

        insert_stmt = insert(NMAHydraulicsData)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into NMA_HydraulicsData"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "PointID": excluded["PointID"],
                    "HydraulicUnit": excluded["HydraulicUnit"],
                    "TestTop": excluded["TestTop"],
                    "TestBottom": excluded["TestBottom"],
                    "HydraulicUnitType": excluded["HydraulicUnitType"],
                    "Hydraulic Remarks": excluded["Hydraulic Remarks"],
                    "T (ft2/d)": excluded["T (ft2/d)"],
                    "S (dimensionless)": excluded["S (dimensionless)"],
                    "Ss (ft-1)": excluded["Ss (ft-1)"],
                    "Sy (decimalfractn)": excluded["Sy (decimalfractn)"],
                    "KH (ft/d)": excluded["KH (ft/d)"],
                    "KV (ft/d)": excluded["KV (ft/d)"],
                    "HL (day-1)": excluded["HL (day-1)"],
                    "HD (ft2/d)": excluded["HD (ft2/d)"],
                    "Cs (gal/d/ft)": excluded["Cs (gal/d/ft)"],
                    "P (decimal fraction)": excluded["P (decimal fraction)"],
                    "k (darcy)": excluded["k (darcy)"],
                    "Data Source": excluded["Data Source"],
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        def val(key: str) -> Optional[Any]:
            v = row.get(key)
            if pd.isna(v):
                return None
            return v

        def as_int(key: str) -> Optional[int]:
            v = val(key)
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        return {
            "GlobalID": val("GlobalID"),
            "PointID": val("PointID"),
            "HydraulicUnit": val("HydraulicUnit"),
            "TestTop": as_int("TestTop"),
            "TestBottom": as_int("TestBottom"),
            "HydraulicUnitType": val("HydraulicUnitType"),
            "Hydraulic Remarks": val("Hydraulic Remarks"),
            "T (ft2/d)": val("T (ft2/d)"),
            "S (dimensionless)": val("S (dimensionless)"),
            "Ss (ft-1)": val("Ss (ft-1)"),
            "Sy (decimalfractn)": val("Sy (decimalfractn)"),
            "KH (ft/d)": val("KH (ft/d)"),
            "KV (ft/d)": val("KV (ft/d)"),
            "HL (day-1)": val("HL (day-1)"),
            "HD (ft2/d)": val("HD (ft2/d)"),
            "Cs (gal/d/ft)": val("Cs (gal/d/ft)"),
            "P (decimal fraction)": val("P (decimal fraction)"),
            "k (darcy)": val("k (darcy)"),
            "Data Source": val("Data Source"),
        }

    def _dedupe_rows(
        self, rows: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """
        Deduplicate rows within a batch by the given key to avoid ON CONFLICT loops.
        Later rows win.
        """
        deduped = {}
        for row in rows:
            gid = row.get(key)
            if gid is None:
                continue
            deduped[gid] = row
        return list(deduped.values())


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the backfill."""
    transferer = NMAHydraulicsDataBackfill(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.backfill.hydraulicsdata`
    run()

# ============= EOF =============================================
