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

import uuid
from typing import Any, Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import SurfaceWaterData
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class SurfaceWaterDataTransferer(Transferer):
    """
    Transfer for the legacy SurfaceWaterData table.
    """

    source_table = "SurfaceWaterData"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = read_csv(
            self.source_table, parse_dates=["DateMeasured"], keep_default_na=False
        )
        return df, df

    def _transfer_hook(self, session: Session) -> None:
        rows = self._dedupe_rows(
            [self._row_dict(row) for row in self.cleaned_df.to_dict("records")],
            key="OBJECTID",
        )

        insert_stmt = insert(SurfaceWaterData)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into SurfaceWaterData"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["OBJECTID"],
                set_={
                    "PointID": excluded.PointID,
                    "OBJECTID": excluded.OBJECTID,
                    "Discharge": excluded.Discharge,
                    "DischargeMethod": excluded.DischargeMethod,
                    "DischargeRate": excluded.DischargeRate,
                    "DischargeUnits": excluded.DischargeUnits,
                    "DateMeasured": excluded.DateMeasured,
                    "DischargeSource": excluded.DischargeSource,
                    "SiteNotes": excluded.SiteNotes,
                    "FieldMethodNotes": excluded.FieldMethodNotes,
                    "FormationZone": excluded.FormationZone,
                    "AqClass": excluded.AqClass,
                    "SourceNotes": excluded.SourceNotes,
                    "DataSource": excluded.DataSource,
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        def is_blank(value: Any) -> bool:
            return isinstance(value, str) and value.strip() == ""

        def val(key: str) -> Optional[Any]:
            v = row.get(key)
            if pd.isna(v):
                return None
            return v

        def as_float(key: str) -> Optional[float]:
            v = val(key)
            if v is None or is_blank(v):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        def to_uuid(v: Any) -> Optional[uuid.UUID]:
            if v is None or pd.isna(v):
                return None
            if isinstance(v, uuid.UUID):
                return v
            if isinstance(v, str) and v.strip():
                return uuid.UUID(v)
            return None

        dt = val("DateMeasured")
        if is_blank(dt):
            dt = None
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()

        return {
            "SurfaceID": to_uuid(val("SurfaceID")),
            "PointID": val("PointID"),
            "OBJECTID": val("OBJECTID"),
            "Discharge": val("Discharge"),
            "DischargeMethod": val("DischargeMethod"),
            "DischargeRate": as_float("DischargeRate"),
            "DischargeUnits": val("DischargeUnits"),
            "DateMeasured": dt,
            "DischargeSource": val("DischargeSource"),
            "SiteNotes": val("SiteNotes"),
            "FieldMethodNotes": val("FieldMethodNotes"),
            "FormationZone": val("FormationZone"),
            "AqClass": val("AqClass"),
            "SourceNotes": val("SourceNotes"),
            "DataSource": val("DataSource"),
        }

    def _dedupe_rows(
        self, rows: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """
        Deduplicate rows within a batch by the given key to avoid ON CONFLICT loops.
        Later rows win.
        """
        deduped: dict[Any, dict[str, Any]] = {}
        passthrough: list[dict[str, Any]] = []
        for row in rows:
            row_key = row.get(key)
            if row_key is None:
                passthrough.append(row)
            else:
                deduped[row_key] = row
        return list(deduped.values()) + passthrough


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = SurfaceWaterDataTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.surface_water_data`
    run()

# ============= EOF =============================================
