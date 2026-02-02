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

from db import NMA_WaterLevelsContinuous_Pressure_Daily, Thing
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class NMA_WaterLevelsContinuous_Pressure_DailyTransferer(Transferer):
    """
    Transfer for the legacy WaterLevelsContinuous_Pressure_Daily table.

    Uses the Transferer utilities to load the CSV into a DataFrame and performs
    a batch insert into the legacy table.
    """

    source_table = "WaterLevelsContinuous_Pressure_Daily"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._thing_id_cache: dict[str, int] = {}
        self._build_thing_id_cache()

    def _build_thing_id_cache(self) -> None:
        with session_ctx() as session:
            things = session.query(Thing.name, Thing.id).all()
            self._thing_id_cache = {name: thing_id for name, thing_id in things}
        logger.info(f"Built Thing ID cache with {len(self._thing_id_cache)} entries")

    def _filter_to_valid_things(self, df: pd.DataFrame) -> pd.DataFrame:
        valid_point_ids = set(self._thing_id_cache.keys())
        before_count = len(df)
        filtered_df = df[df["PointID"].isin(valid_point_ids)].copy()
        after_count = len(filtered_df)
        if before_count > after_count:
            skipped = before_count - after_count
            logger.warning(
                "Filtered out %s WaterLevelsContinuous_Pressure_Daily records without matching Things "
                "(%s valid, %s orphan records prevented)",
                skipped,
                after_count,
                skipped,
            )
        return filtered_df

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Parse key datetime columns eagerly to avoid per-row parsing later.
        input_df = read_csv(
            self.source_table,
            parse_dates=["DateMeasured", "Created", "Updated"],
        )
        cleaned_df = self._filter_to_valid_things(input_df)
        return input_df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        rows = self._dedupe_rows(
            [self._row_dict(row) for row in self.cleaned_df.to_dict("records")],
            key="GlobalID",
        )

        insert_stmt = insert(NMA_WaterLevelsContinuous_Pressure_Daily)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into NMA_WaterLevelsContinuous_Pressure_Daily"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "OBJECTID": excluded.OBJECTID,
                    "WellID": excluded.WellID,
                    "PointID": excluded.PointID,
                    "thing_id": excluded.thing_id,
                    "DateMeasured": excluded.DateMeasured,
                    "TemperatureWater": excluded.TemperatureWater,
                    "WaterHead": excluded.WaterHead,
                    "WaterHeadAdjusted": excluded.WaterHeadAdjusted,
                    "DepthToWaterBGS": excluded.DepthToWaterBGS,
                    "MeasurementMethod": excluded.MeasurementMethod,
                    "DataSource": excluded.DataSource,
                    "MeasuringAgency": excluded.MeasuringAgency,
                    "QCed": excluded.QCed,
                    "Notes": excluded.Notes,
                    "Created": excluded.Created,
                    "Updated": excluded.Updated,
                    "ProcessedBy": excluded.ProcessedBy,
                    "CheckedBy": excluded.CheckedBy,
                    "CONDDL (mS/cm)": excluded["CONDDL (mS/cm)"],
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

        return {
            "GlobalID": val("GlobalID"),
            "OBJECTID": val("OBJECTID"),
            "WellID": val("WellID"),
            "PointID": val("PointID"),
            "thing_id": self._thing_id_cache.get(val("PointID")),
            "DateMeasured": val("DateMeasured"),
            "TemperatureWater": val("TemperatureWater"),
            "WaterHead": val("WaterHead"),
            "WaterHeadAdjusted": val("WaterHeadAdjusted"),
            "DepthToWaterBGS": val("DepthToWaterBGS"),
            "MeasurementMethod": val("MeasurementMethod"),
            "DataSource": val("DataSource"),
            "MeasuringAgency": val("MeasuringAgency"),
            "QCed": val("QCed"),
            "Notes": val("Notes"),
            "Created": val("Created"),
            "Updated": val("Updated"),
            "ProcessedBy": val("ProcessedBy"),
            "CheckedBy": val("CheckedBy"),
            "CONDDL (mS/cm)": val("CONDDL (mS/cm)"),
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
    """Entrypoint to execute the transfer."""
    transferer = NMA_WaterLevelsContinuous_Pressure_DailyTransferer(
        batch_size=batch_size
    )
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.waterlevelscontinuous_pressure_daily`
    run()

# ============= EOF =============================================
