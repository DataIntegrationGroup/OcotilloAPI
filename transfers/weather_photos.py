# ==============================================================================
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
# ==============================================================================

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import NMA_WeatherData, NMA_WeatherPhotos
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import replace_nans


class WeatherPhotosTransferer(Transferer):
    """Transfer legacy WeatherPhotos rows from NM_Aquifer."""

    source_table = "WeatherPhotos"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._weather_id_cache: set[str] = set()
        self._build_weather_id_cache()

    def _build_weather_id_cache(self) -> None:
        with session_ctx() as session:
            weather_ids = session.query(NMA_WeatherData.weather_id).all()
            for (weather_id,) in weather_ids:
                if weather_id:
                    self._weather_id_cache.add(self._normalize_weather_id(weather_id))
        logger.info(
            "Built WeatherData cache with %s weather ids",
            len(self._weather_id_cache),
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = self._read_csv(self.source_table)
        cleaned_df = replace_nans(df)
        return df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        rows: list[dict[str, Any]] = []
        skipped_missing_parent = 0
        for raw in self.cleaned_df.to_dict("records"):
            record = self._row_dict(raw)
            if record is None:
                skipped_missing_parent += 1
                continue
            rows.append(record)
        rows = self._dedupe_rows(rows, key="GlobalID")

        if not rows:
            logger.info("No WeatherPhotos rows to transfer")
            return
        if skipped_missing_parent:
            logger.warning(
                "Skipped %s WeatherPhotos rows without matching WeatherData",
                skipped_missing_parent,
            )

        insert_stmt = insert(NMA_WeatherPhotos)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                "Upserting WeatherPhotos rows %s-%s (%s rows)",
                i,
                i + len(chunk) - 1,
                len(chunk),
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "WeatherID": excluded["WeatherID"],
                    "PointID": excluded["PointID"],
                    "OLEPath": excluded["OLEPath"],
                    "OBJECTID": excluded["OBJECTID"],
                },
            )
            session.execute(stmt)
        session.commit()

    def _row_dict(self, row: dict[str, Any]) -> Optional[dict[str, Any]]:
        weather_id = self._uuid_val(row.get("WeatherID"))
        if weather_id is None or not self._has_weather_id(weather_id):
            logger.warning(
                "Skipping WeatherPhotos WeatherID=%s - WeatherData not found",
                weather_id,
            )
            return None
        return {
            "WeatherID": weather_id,
            "PointID": row.get("PointID"),
            "OLEPath": row.get("OLEPath"),
            "OBJECTID": row.get("OBJECTID"),
            "GlobalID": self._uuid_val(row.get("GlobalID")),
        }

    def _dedupe_rows(
        self, rows: list[dict[str, Any]], key: str
    ) -> list[dict[str, Any]]:
        """Dedupe rows by unique key to avoid ON CONFLICT loops. Later rows win."""
        deduped = {}
        for row in rows:
            global_id = row.get(key)
            if global_id is None:
                continue
            deduped[global_id] = row
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

    def _has_weather_id(self, weather_id: UUID) -> bool:
        return self._normalize_weather_id(weather_id) in self._weather_id_cache

    @staticmethod
    def _normalize_weather_id(value: UUID) -> str:
        return str(value).strip().lower()


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = WeatherPhotosTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    run()

# ============= EOF =============================================
