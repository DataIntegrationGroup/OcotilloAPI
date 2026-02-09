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

from db import NMA_WeatherData
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class WeatherDataTransferer(Transferer):
    """
    Transfer for the legacy WeatherData table.
    """

    source_table = "WeatherData"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = read_csv(self.source_table)
        return df, df

    def _transfer_hook(self, session: Session) -> None:
        rows = self._dedupe_rows(
            [self._row_dict(row) for row in self.cleaned_df.to_dict("records")],
            key="OBJECTID",
            include_missing=True,
        )

        insert_stmt = insert(NMA_WeatherData)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into WeatherData"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["OBJECTID"],
                set_={
                    "LocationId": excluded.LocationId,
                    "PointID": excluded.PointID,
                    "WeatherID": excluded.WeatherID,
                    "OBJECTID": excluded.OBJECTID,
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

        def to_uuid(v: Any) -> Optional[uuid.UUID]:
            if v is None or pd.isna(v):
                return None
            if isinstance(v, uuid.UUID):
                return v
            if isinstance(v, str) and v.strip():
                return uuid.UUID(v)
            return None

        return {
            "LocationId": to_uuid(val("LocationId")),
            "PointID": val("PointID"),
            "WeatherID": to_uuid(val("WeatherID")),
            "OBJECTID": val("OBJECTID"),
        }


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = WeatherDataTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.weather_data`
    run()

# ============= EOF =============================================
