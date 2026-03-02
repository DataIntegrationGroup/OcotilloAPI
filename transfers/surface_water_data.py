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

from db import NMA_SurfaceWaterData, Thing
from db.engine import session_ctx
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
        self._thing_id_by_location_id: dict[str, int] = {}
        self._build_thing_id_cache()

    def _build_thing_id_cache(self) -> None:
        with session_ctx() as session:
            things = session.query(Thing.id, Thing.nma_pk_location).all()
            for thing_id, nma_pk_location in things:
                if nma_pk_location:
                    key = self._normalize_location_id(nma_pk_location)
                    if key:
                        self._thing_id_by_location_id[key] = thing_id
        logger.info(
            "Built Thing cache with %s location ids",
            len(self._thing_id_by_location_id),
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = read_csv(self.source_table, parse_dates=["DateMeasured"])
        return df, df

    def _transfer_hook(self, session: Session) -> None:
        rows: list[dict[str, Any]] = []
        skipped_missing_thing = 0
        for raw in self.cleaned_df.to_dict("records"):
            record = self._row_dict(raw)
            if record is None:
                skipped_missing_thing += 1
                continue
            rows.append(record)

        if skipped_missing_thing:
            logger.warning(
                "Skipped %s SurfaceWaterData rows without matching Thing",
                skipped_missing_thing,
            )

        if not rows:
            logger.info("No SurfaceWaterData rows to transfer")
            return

        rows = self._dedupe_rows(rows, key="OBJECTID", include_missing=True)

        insert_stmt = insert(NMA_SurfaceWaterData)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into SurfaceWaterData"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["OBJECTID"],
                set_={
                    "thing_id": excluded["thing_id"],
                    "LocationId": excluded.LocationId,
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

    def _row_dict(self, row: dict[str, Any]) -> Optional[dict[str, Any]]:
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

        dt = val("DateMeasured")
        if hasattr(dt, "to_pydatetime"):
            dt = dt.to_pydatetime()

        location_id = to_uuid(val("LocationId"))
        thing_id = self._resolve_thing_id(location_id)
        if thing_id is None:
            logger.warning(
                "Skipping SurfaceWaterData OBJECTID=%s PointID=%s LocationId=%s - Thing not found",
                val("OBJECTID"),
                val("PointID"),
                location_id,
            )
            return None

        return {
            "LocationId": location_id,
            "SurfaceID": to_uuid(val("SurfaceID")),
            "PointID": val("PointID"),
            "OBJECTID": val("OBJECTID"),
            "Discharge": val("Discharge"),
            "DischargeMethod": val("DischargeMethod"),
            "DischargeRate": val("DischargeRate"),
            "DischargeUnits": val("DischargeUnits"),
            "DateMeasured": dt,
            "DischargeSource": val("DischargeSource"),
            "SiteNotes": val("SiteNotes"),
            "FieldMethodNotes": val("FieldMethodNotes"),
            "FormationZone": val("FormationZone"),
            "AqClass": val("AqClass"),
            "SourceNotes": val("SourceNotes"),
            "DataSource": val("DataSource"),
            "thing_id": thing_id,
        }

    def _resolve_thing_id(self, location_id: Optional[uuid.UUID]) -> Optional[int]:
        if location_id is None:
            return None
        key = self._normalize_location_id(str(location_id))
        return self._thing_id_by_location_id.get(key)

    @staticmethod
    def _normalize_location_id(value: str) -> str:
        return value.strip().lower()


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the transfer."""
    transferer = SurfaceWaterDataTransferer(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.surface_water_data`
    run()

# ============= EOF =============================================
