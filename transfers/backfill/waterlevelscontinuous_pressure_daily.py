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
from sqlalchemy.orm import Session

from db import NMAWaterLevelsContinuousPressureDaily
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class NMAWaterLevelsContinuousPressureDailyBackfill(Transferer):
    """
    Backfill for the legacy WaterLevelsContinuous_Pressure_Daily table.

    Uses the Transferer utilities to load the CSV into a DataFrame and performs
    a batch insert into the legacy table.
    """

    source_table = "WaterLevelsContinuous_Pressure_Daily"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Parse key datetime columns eagerly to avoid per-row parsing later.
        input_df = read_csv(
            self.source_table,
            parse_dates=["DateMeasured", "Created", "Updated"],
        )
        # No special cleaning/validation beyond raw import; keep identical copy.
        return input_df, input_df

    def _transfer_hook(self, session: Session) -> None:
        records: list[NMAWaterLevelsContinuousPressureDaily] = []

        for i, row in enumerate(self.cleaned_df.to_dict("records")):
            records.append(self._make_model(row))

            if len(records) >= self.batch_size:
                logger.info(f"Inserting batch ending at row {i} ({len(records)} rows)")
                session.bulk_save_objects(records)
                session.commit()
                session.expunge_all()
                records.clear()

        if records:
            logger.info(f"Inserting final batch of {len(records)} rows")
            session.bulk_save_objects(records)
            session.commit()
            session.expunge_all()

    def _make_model(self, row: dict[str, Any]) -> NMAWaterLevelsContinuousPressureDaily:
        def val(key: str) -> Optional[Any]:
            v = row.get(key)
            if pd.isna(v):
                return None
            return v

        return NMAWaterLevelsContinuousPressureDaily(
            global_id=val("GlobalID"),
            object_id=val("OBJECTID"),
            well_id=val("WellID"),
            point_id=val("PointID"),
            date_measured=val("DateMeasured"),
            temperature_water=val("TemperatureWater"),
            water_head=val("WaterHead"),
            water_head_adjusted=val("WaterHeadAdjusted"),
            depth_to_water_bgs=val("DepthToWaterBGS"),
            measurement_method=val("MeasurementMethod"),
            data_source=val("DataSource"),
            measuring_agency=val("MeasuringAgency"),
            qced=val("QCed"),
            notes=val("Notes"),
            created=val("Created"),
            updated=val("Updated"),
            processed_by=val("ProcessedBy"),
            checked_by=val("CheckedBy"),
            cond_dl_ms_cm=val("CONDDL (mS/cm)"),
        )


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the backfill."""
    transferer = NMAWaterLevelsContinuousPressureDailyBackfill(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.backfill.waterlevelscontinuous_pressure_daily`
    run()

# ============= EOF =============================================
