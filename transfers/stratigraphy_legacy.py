"""Transfer Stratigraphy.csv into the NMA_Stratigraphy legacy table."""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from db import NMA_Stratigraphy, Thing
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import (
    filter_to_valid_point_ids,
    read_csv,
    replace_nans,
)


class StratigraphyLegacyTransferer(Transferer):
    """Imports Stratigraphy.csv rows into NMA_Stratigraphy."""

    source_table = "Stratigraphy"

    def __init__(self, batch_size: int = 1000, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self._thing_id_cache: dict[str, int] = {}

    def _get_dfs(self):  # type: ignore[override]
        df = read_csv(self.source_table)
        cleaned = replace_nans(df)
        cleaned = filter_to_valid_point_ids(cleaned, self.pointids)
        return df, cleaned

    def _transfer_hook(self, session: Session) -> None:  # type: ignore[override]
        if self.cleaned_df is None or self.cleaned_df.empty:
            logger.info("No Stratigraphy rows to import after cleaning")
            return

        self._prime_thing_cache(session)
        rows: List[Dict[str, Any]] = []
        for row in self.cleaned_df.itertuples():
            record = self._row_dict(row)
            if record is None:
                continue
            rows.append(record)

        if not rows:
            logger.warning("All Stratigraphy rows were skipped during processing")
            return

        insert_stmt = insert(NMA_Stratigraphy)
        excluded = insert_stmt.excluded

        for start in range(0, len(rows), self.batch_size):
            chunk = rows[start : start + self.batch_size]
            logger.info(
                "Upserting Stratigraphy batch %s-%s (%s rows)",
                start,
                start + len(chunk) - 1,
                len(chunk),
            )
            stmt = insert_stmt.values(chunk).on_conflict_do_update(
                index_elements=["GlobalID"],
                set_={
                    "WellID": excluded.WellID,
                    "PointID": excluded.PointID,
                    "thing_id": excluded.thing_id,
                    "StratTop": excluded.StratTop,
                    "StratBottom": excluded.StratBottom,
                    "UnitIdentifier": excluded.UnitIdentifier,
                    "Lithology": excluded.Lithology,
                    "LithologicModifier": excluded.LithologicModifier,
                    "ContributingUnit": excluded.ContributingUnit,
                    "StratSource": excluded.StratSource,
                    "StratNotes": excluded.StratNotes,
                    "OBJECTID": excluded.OBJECTID,
                },
            )
            session.execute(stmt)
            session.commit()
            session.expunge_all()

    def _prime_thing_cache(self, session: Session) -> None:
        point_ids = set(self.cleaned_df["PointID"].dropna())  # type: ignore[index]
        if not point_ids:
            self._thing_id_cache = {}
            return
        results = (
            session.query(Thing.id, Thing.name).filter(Thing.name.in_(point_ids)).all()
        )
        self._thing_id_cache = {name: thing_id for thing_id, name in results}

    def _row_dict(self, row: pd.Series) -> Dict[str, Any] | None:
        point_id = getattr(row, "PointID", None)
        if not point_id:
            self._capture_error("<missing>", "Missing PointID", "PointID")
            return None
        thing_id = self._thing_id_cache.get(point_id)
        if not thing_id:
            self._capture_error(point_id, "No Thing found for PointID", "thing_id")
            return None

        global_id = self._uuid_value(getattr(row, "GlobalID", None))
        if global_id is None:
            self._capture_error(point_id, "Invalid GlobalID", "GlobalID")
            return None

        return {
            "GlobalID": global_id,
            "WellID": self._uuid_value(getattr(row, "WellID", None)),
            "PointID": point_id,
            "thing_id": thing_id,
            "StratTop": self._float_value(getattr(row, "StratTop", None)),
            "StratBottom": self._float_value(getattr(row, "StratBottom", None)),
            "UnitIdentifier": self._string_value(getattr(row, "UnitIdentifier", None)),
            "Lithology": self._string_value(getattr(row, "Lithology", None)),
            "LithologicModifier": self._string_value(
                getattr(row, "LithologicModifier", None)
            ),
            "ContributingUnit": self._string_value(
                getattr(row, "ContributingUnit", None)
            ),
            "StratSource": self._string_value(getattr(row, "StratSource", None)),
            "StratNotes": self._string_value(getattr(row, "StratNotes", None)),
            "OBJECTID": self._int_value(getattr(row, "OBJECTID", None)),
        }

    def _uuid_value(self, value: Any) -> UUID | None:
        if value in (None, ""):
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

    def _float_value(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _int_value(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _string_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return str(value)
