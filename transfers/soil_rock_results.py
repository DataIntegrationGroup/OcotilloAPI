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
"""
Transfer Soil_Rock_Results from NM_Aquifer to NMA_Soil_Rock_Results.

Already has Integer PK. Updated for legacy column rename:
- point_id -> nma_point_id
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from db import NMA_Soil_Rock_Results, Thing
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import replace_nans


class SoilRockResultsTransferer(Transferer):
    """Transfer legacy Soil_Rock_Results rows from NM_Aquifer."""

    source_table = "Soil_Rock_Results"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._thing_id_by_point_id: dict[str, int] = {}
        self._thing_id_by_location_id: dict[str, int] = {}
        self._build_thing_id_cache()

    def _build_thing_id_cache(self) -> None:
        with session_ctx() as session:
            things = session.query(Thing.id, Thing.name, Thing.nma_pk_location).all()
            for thing_id, name, nma_pk_location in things:
                if name:
                    point_key = self._normalize_point_id(name)
                    if point_key:
                        self._thing_id_by_point_id[point_key] = thing_id
                if nma_pk_location:
                    loc_key = self._normalize_location_id(nma_pk_location)
                    if loc_key:
                        self._thing_id_by_location_id[loc_key] = thing_id
        logger.info(
            "Built Thing caches with %s point ids and %s location ids",
            len(self._thing_id_by_point_id),
            len(self._thing_id_by_location_id),
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = self._read_csv(self.source_table)
        cleaned_df = replace_nans(df)
        if self.is_scoped_run():
            normalized_pointids = cleaned_df["Point_ID"].map(self._normalize_point_id)
            cleaned_df = cleaned_df[normalized_pointids.isin(self.scoped_pointid_set())]
        return df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        rows: list[dict[str, Any]] = []
        skipped_missing_thing = 0
        for raw in self.cleaned_df.to_dict("records"):
            record = self._row_dict(raw)
            if record is None:
                skipped_missing_thing += 1
                continue
            rows.append(record)

        if not rows:
            logger.info("No Soil_Rock_Results rows to transfer")
            return

        if skipped_missing_thing:
            logger.warning(
                "Skipped %s Soil_Rock_Results rows without matching Thing",
                skipped_missing_thing,
            )

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                "Inserting Soil_Rock_Results rows %s-%s (%s rows)",
                i,
                i + len(chunk) - 1,
                len(chunk),
            )
            session.bulk_insert_mappings(NMA_Soil_Rock_Results, chunk)
            session.commit()

    def _row_dict(self, row: dict[str, Any]) -> Optional[dict[str, Any]]:
        point_id = row.get("Point_ID")
        thing_id = self._resolve_thing_id(point_id)
        if thing_id is None:
            logger.warning(
                "Skipping Soil_Rock_Results Point_ID=%s - Thing not found",
                point_id,
            )
            return None

        return {
            # Legacy ID column (use Python attribute name for bulk_insert_mappings)
            "nma_point_id": point_id,
            # Data columns (use Python attribute names, not database column names)
            "sample_type": row.get("Sample Type"),
            "date_sampled": row.get("Date Sampled"),
            "d13c": self._float_val(row.get("d13C")),
            "d18o": self._float_val(row.get("d18O")),
            "sampled_by": row.get("Sampled by"),
            # FK to Thing
            "thing_id": thing_id,
        }

    def _resolve_thing_id(self, point_id: Optional[str]) -> Optional[int]:
        if point_id is None:
            return None

        key = self._normalize_location_id(point_id)
        thing_id = self._thing_id_by_location_id.get(key)
        if thing_id is not None:
            return thing_id

        return self._thing_id_by_point_id.get(self._normalize_point_id(point_id))

    @staticmethod
    def _normalize_point_id(value: str) -> str:
        return str(value).strip().upper()

    @staticmethod
    def _normalize_location_id(value: str) -> str:
        return str(value).strip().lower()

    def _float_val(self, value: Any) -> Optional[float]:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                return None
        return None


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = SoilRockResultsTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    run()

# ============= EOF =============================================
