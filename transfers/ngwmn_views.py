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

from db import (
    NMA_view_NGWMN_Lithology,
    NMA_view_NGWMN_WaterLevels,
    NMA_view_NGWMN_WellConstruction,
)
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import read_csv, filter_to_valid_point_ids


class _BaseNGWMNTransferer(Transferer):
    """
    Base class for transferring legacy NGWMN view tables from CSVs in GCS.
    """

    model = None
    parse_dates: list[str] | None = None

    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        df = read_csv(self.source_table, parse_dates=self.parse_dates)
        cleaned_df = filter_to_valid_point_ids(df, self.pointids)
        return df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        rows = self._dedupe_rows(
            [self._row_dict(row) for row in self.cleaned_df.to_dict("records")],
            key=self._conflict_columns(),
            include_missing=True,
        )

        for i in range(0, len(rows), self.batch_size):
            chunk = rows[i : i + self.batch_size]
            logger.info(
                f"Upserting batch {i}-{i+len(chunk)-1} ({len(chunk)} rows) into {self.model.__tablename__}"
            )
            stmt = (
                insert(self.model)
                .values(chunk)
                .on_conflict_do_update(
                    index_elements=self._conflict_columns(),
                    set_=self._upsert_set_clause(),
                )
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("_row_dict must be implemented in subclasses")

    @staticmethod
    def _val(row: dict[str, Any], key: str) -> Optional[Any]:
        v = row.get(key)
        if pd.isna(v):
            return None
        return v

    @staticmethod
    def _float_or_none(v: Any) -> Optional[float]:
        if v is None or pd.isna(v):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            import re

            match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", v)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
        return None

    def _conflict_columns(self) -> list[str]:
        raise NotImplementedError("_conflict_columns must be implemented")

    def _upsert_set_clause(self) -> dict[str, Any]:
        raise NotImplementedError("_upsert_set_clause must be implemented")


class NGWMNWellConstructionTransferer(_BaseNGWMNTransferer):
    source_table = "view_NGWMN_WellConstruction"
    model = NMA_view_NGWMN_WellConstruction

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        val = self._val
        f = self._float_or_none
        return {
            "PointID": val(row, "PointID"),
            "CasingTop": f(val(row, "CasingTop")),
            "CasingBottom": f(val(row, "CasingBottom")),
            "CasingDepthUnits": val(row, "CasingDepthUnits"),
            "ScreenTop": f(val(row, "ScreenTop")),
            "ScreenBottom": f(val(row, "ScreenBottom")),
            "ScreenBottomUnit": val(row, "ScreenBottomUnit"),
            "ScreenDescription": val(row, "ScreenDescription"),
            "CasingDescription": val(row, "CasingDescription"),
        }

    def _conflict_columns(self) -> list[str]:
        return ["PointID", "CasingTop", "ScreenTop"]

    def _upsert_set_clause(self) -> dict[str, Any]:
        excluded = insert(self.model).excluded
        return {
            "CasingBottom": excluded.CasingBottom,
            "CasingDepthUnits": excluded.CasingDepthUnits,
            "ScreenBottom": excluded.ScreenBottom,
            "ScreenBottomUnit": excluded.ScreenBottomUnit,
            "ScreenDescription": excluded.ScreenDescription,
            "CasingDescription": excluded.CasingDescription,
        }


class NGWMNWaterLevelsTransferer(_BaseNGWMNTransferer):
    source_table = "view_NGWMN_WaterLevels"
    model = NMA_view_NGWMN_WaterLevels
    parse_dates = ["DateMeasured"]

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        val = self._val
        f = self._float_or_none
        dm = val(row, "DateMeasured")
        if hasattr(dm, "date"):
            dm = dm.date()
        return {
            "PointID": val(row, "PointID"),
            "DateMeasured": dm,
            "DepthToWaterBGS": f(val(row, "DepthToWaterBGS")),
            "WLUnits": val(row, "WLUnits"),
            "MeasurementMethod": val(row, "MeasurementMethod"),
            "WLAccuracy": f(val(row, "WLAccuracy")),
            "PublicRelease": val(row, "PublicRelease"),
        }

    def _conflict_columns(self) -> list[str]:
        return ["PointID", "DateMeasured"]

    def _upsert_set_clause(self) -> dict[str, Any]:
        excluded = insert(self.model).excluded
        return {
            "DepthToWaterBGS": excluded.DepthToWaterBGS,
            "WLUnits": excluded.WLUnits,
            "MeasurementMethod": excluded.MeasurementMethod,
            "WLAccuracy": excluded.WLAccuracy,
            "PublicRelease": excluded.PublicRelease,
        }


class NGWMNLithologyTransferer(_BaseNGWMNTransferer):
    source_table = "view_NGWMN_Lithology"
    model = NMA_view_NGWMN_Lithology

    def _row_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        val = self._val
        f = self._float_or_none
        return {
            "OBJECTID": val(row, "OBJECTID"),
            "PointID": val(row, "PointID"),
            "Lithology": val(row, "Lithology"),
            "TERM": val(row, "TERM"),
            "StratSource": val(row, "StratSource"),
            "StratTop": f(val(row, "StratTop")),
            "StratTopUnit": val(row, "StratTopUnit"),
            "StratBottom": f(val(row, "StratBottom")),
            "StratBottomUnit": val(row, "StratBottomUnit"),
        }

    def _conflict_columns(self) -> list[str]:
        return ["OBJECTID"]

    def _upsert_set_clause(self) -> dict[str, Any]:
        excluded = insert(self.model).excluded
        return {
            "PointID": excluded.PointID,
            "Lithology": excluded.Lithology,
            "TERM": excluded.TERM,
            "StratSource": excluded.StratSource,
            "StratTop": excluded.StratTop,
            "StratTopUnit": excluded.StratTopUnit,
            "StratBottom": excluded.StratBottom,
            "StratBottomUnit": excluded.StratBottomUnit,
        }


def run(batch_size: int = 1000) -> None:
    """
    Entrypoint to transfer all NGWMN view tables.

    Tables are processed sequentially to keep memory use bounded.
    """

    for transfer_cls in (
        NGWMNWellConstructionTransferer,
        NGWMNWaterLevelsTransferer,
        NGWMNLithologyTransferer,
    ):
        logger.info(f"Starting {transfer_cls.__name__}")
        transferer = transfer_cls(batch_size=batch_size)
        transferer.transfer()
        logger.info(f"Finished {transfer_cls.__name__}")


if __name__ == "__main__":
    run()

# ============= EOF =============================================
