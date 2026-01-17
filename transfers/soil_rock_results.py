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

import pandas as pd
from sqlalchemy.orm import Session

from db import SoilRockResults, Thing
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
        self._thing_id_cache: dict[str, int] = {}
        self._build_thing_id_cache()

    def _build_thing_id_cache(self) -> None:
        with session_ctx() as session:
            things = session.query(Thing.name, Thing.id).all()
            self._thing_id_cache = {name: thing_id for name, thing_id in things}
        logger.info(f"Built Thing ID cache with {len(self._thing_id_cache)} entries")

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = self._read_csv(self.source_table)
        cleaned_df = replace_nans(df)
        return df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        rows = [self._row_dict(row) for row in self.cleaned_df.to_dict("records")]

        if not rows:
            logger.info("No Soil_Rock_Results rows to transfer")
            return

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                "Inserting Soil_Rock_Results rows %s-%s (%s rows)",
                i,
                i + len(chunk) - 1,
                len(chunk),
            )
            session.bulk_insert_mappings(SoilRockResults, chunk)
            session.commit()

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "Point_ID": row.get("Point_ID"),
            "Sample Type": row.get("Sample Type"),
            "Date Sampled": row.get("Date Sampled"),
            "d13C": self._float_val(row.get("d13C")),
            "d18O": self._float_val(row.get("d18O")),
            "Sampled by": row.get("Sampled by"),
            "thing_id": self._thing_id_cache.get(row.get("Point_ID")),
        }

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
