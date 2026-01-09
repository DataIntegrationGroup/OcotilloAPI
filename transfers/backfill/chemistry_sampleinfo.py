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

from db import ChemistrySampleInfo, Thing
from db.engine import session_ctx
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv


class ChemistrySampleInfoBackfill(Transferer):
    """
    Backfill for the legacy Chemistry_SampleInfo table.

    Loads the CSV and upserts into the legacy table for backfill workflows.
    """

    source_table = "Chemistry_SampleInfo"

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        # Cache Thing lookups to prevent N+1 queries
        self._thing_id_cache = {}
        self._build_thing_id_cache()
    
    def _build_thing_id_cache(self):
        """Build cache of Thing.name -> thing.id to prevent orphan records."""
        with session_ctx() as session:
            things = session.query(Thing.name, Thing.id).all()
            self._thing_id_cache = {name: thing_id for name, thing_id in things}
        logger.info(f"Built Thing ID cache with {len(self._thing_id_cache)} entries")

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = read_csv(self.source_table, parse_dates=["CollectionDate"])
        # Filter to only include rows where Thing exists (prevent orphan records)
        cleaned_df = self._filter_to_valid_things(input_df)
        return input_df, cleaned_df
    
    def _filter_to_valid_things(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to only include rows where SamplePointID matches an existing Thing.
        Prevents orphan ChemistrySampleInfo records.
        
        Uses cached Thing lookups for performance.
        """
        # Use cached Thing names (keys of thing_id_cache)
        valid_point_ids = set(self._thing_id_cache.keys())
        
        # Filter to rows where SamplePointID exists as a Thing.name
        before_count = len(df)
        filtered_df = df[df["SamplePointID"].isin(valid_point_ids)].copy()
        after_count = len(filtered_df)
        
        if before_count > after_count:
            skipped = before_count - after_count
            logger.warning(
                f"Filtered out {skipped} ChemistrySampleInfo records without matching Things "
                f"({after_count} valid, {skipped} orphan records prevented)"
            )
        
        return filtered_df

    def _transfer_hook(self, session: Session) -> None:
        # Convert rows to dicts and filter out any without valid thing_id
        row_dicts = []
        skipped_count = 0
        for row in self.cleaned_df.to_dict("records"):
            row_dict = self._row_dict(row)
            # Skip rows without valid thing_id (orphan prevention)
            if row_dict.get("thing_id") is None:
                skipped_count += 1
                logger.warning(
                    f"Skipping ChemistrySampleInfo OBJECTID={row_dict.get('OBJECTID')} "
                    f"SamplePointID={row_dict.get('SamplePointID')} - Thing not found"
                )
                continue
            row_dicts.append(row_dict)
        
        if skipped_count > 0:
            logger.warning(
                f"Skipped {skipped_count} ChemistrySampleInfo records without valid Thing "
                f"(orphan prevention)"
            )
        
        rows = self._dedupe_rows(row_dicts, key="OBJECTID")

        insert_stmt = insert(ChemistrySampleInfo)
        excluded = insert_stmt.excluded

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into Chemistry_SampleInfo"
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["OBJECTID"],
                set_={
                    "thing_id": excluded.thing_id,  # Required FK - prevent orphans
                    "SamplePointID": excluded.SamplePointID,
                    "SamplePtID": excluded.SamplePtID,
                    "WCLab_ID": excluded.WCLab_ID,
                    "CollectionDate": excluded.CollectionDate,
                    "CollectionMethod": excluded.CollectionMethod,
                    "CollectedBy": excluded.CollectedBy,
                    "AnalysesAgency": excluded.AnalysesAgency,
                    "SampleType": excluded.SampleType,
                    "SampleMaterialNotH2O": excluded.SampleMaterialNotH2O,
                    "WaterType": excluded.WaterType,
                    "StudySample": excluded.StudySample,
                    "DataSource": excluded.DataSource,
                    "DataQuality": excluded.DataQuality,
                    "PublicRelease": excluded.PublicRelease,
                    "AddedDaytoDate": excluded.AddedDaytoDate,
                    "AddedMonthDaytoDate": excluded.AddedMonthDaytoDate,
                    "SampleNotes": excluded.SampleNotes,
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

        def bool_val(key: str) -> Optional[bool]:
            v = val(key)
            if v is None:
                return None
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(int(v))
            if isinstance(v, str):
                normalized = v.strip().lower()
                if normalized in {"y", "yes", "true", "t", "1"}:
                    return True
                if normalized in {"n", "no", "false", "f", "0"}:
                    return False
            return None

        collection_date = val("CollectionDate")
        if hasattr(collection_date, "date"):
            collection_date = collection_date.date()

        # Look up Thing by SamplePointID to prevent orphan records
        sample_point_id = val("SamplePointID")
        thing_id = None
        if sample_point_id and sample_point_id in self._thing_id_cache:
            thing_id = self._thing_id_cache[sample_point_id]
        # If Thing not found, thing_id remains None and will be filtered out

        return {
            "OBJECTID": val("OBJECTID"),
            "thing_id": thing_id,  # Required FK - prevents orphan records
            "SamplePointID": val("SamplePointID"),
            "SamplePtID": val("SamplePtID"),
            "WCLab_ID": val("WCLab_ID"),
            "CollectionDate": collection_date,
            "CollectionMethod": val("CollectionMethod"),
            "CollectedBy": val("CollectedBy"),
            "AnalysesAgency": val("AnalysesAgency"),
            "SampleType": val("SampleType"),
            "SampleMaterialNotH2O": bool_val("SampleMaterialNotH2O"),
            "WaterType": val("WaterType"),
            "StudySample": bool_val("StudySample"),
            "DataSource": val("DataSource"),
            "DataQuality": val("DataQuality"),
            "PublicRelease": bool_val("PublicRelease"),
            "AddedDaytoDate": val("AddedDaytoDate"),
            "AddedMonthDaytoDate": val("AddedMonthDaytoDate"),
            "SampleNotes": val("SampleNotes"),
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
            oid = row.get(key)
            if oid is None:
                continue
            deduped[oid] = row
        return list(deduped.values())


def run(batch_size: int = 1000) -> None:
    """Entrypoint to execute the backfill."""
    transferer = ChemistrySampleInfoBackfill(batch_size=batch_size)
    transferer.transfer()


if __name__ == "__main__":
    # Allow running via `python -m transfers.backfill.chemistry_sampleinfo`
    run()

# ============= EOF =============================================
