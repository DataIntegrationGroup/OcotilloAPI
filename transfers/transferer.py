# ===============================================================================
# Copyright 2025 ross
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
import time
from typing import Any, Optional
from uuid import UUID

import pandas as pd
from pandas import DataFrame
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from db import Thing, Base, NMA_Chemistry_SampleInfo
from db.engine import session_ctx
from transfers.logger import logger
from transfers.util import chunk_by_size, read_csv


class ManualFixer(object):
    pass


class Transferer(object):
    input_df: pd.DataFrame = None
    cleaned_df: pd.DataFrame = None
    errors: list = None
    flags: dict = None
    source_table: str = None
    verbose: bool = False

    def __init__(self, flags: dict = None, pointids: list = None):
        self.errors = []
        self.flags = flags if flags else {}
        self.manual_fixer = ManualFixer()
        self.pointids = pointids

    def _df_len(self, df: pd.DataFrame | None) -> int:
        return int(len(df)) if df is not None else 0

    def transfer(self) -> None:
        with session_ctx() as session:
            name = self.source_table or self.__class__.__name__
            logger.info("Starting transfer: %s", name)
            self.input_df, self.cleaned_df = self._get_dfs()
            logger.info(
                "Loaded %s rows (%s cleaned) for %s",
                self._df_len(self.input_df),
                self._df_len(self.cleaned_df),
                name,
            )
            self._transfer_hook(session)
            session.commit()
            logger.info("Completed transfer: %s", name)

    def _capture_validation_error(self, pointid: str, err: ValidationError) -> None:
        self._capture_error(
            pointid, f"Validation Error: {err.errors()}", "UnknownField"
        )

    def _capture_database_error(self, pointid: str, err: DatabaseError) -> None:
        error_dict = err.orig.args[0]
        self._capture_error(pointid, error_dict["D"], error_dict["t"])

    def _capture_error(self, pointid: str, error: str, field: str, table=None) -> None:
        if table is None:
            table = self.source_table

        logger.critical(
            f"Capture Error: PointID={pointid}, Error: {error}, {table}:{field}"
        )
        self.errors.append(
            {
                "pointid": pointid,
                "error": error,
                "table": table,
                "field": field,
            }
        )

    def _transfer_hook(self, session: Session):
        self._limit_iterator(session, self.flags.get("LIMIT", 0))

    def _get_df_to_iterate(self) -> pd.DataFrame:
        return self.cleaned_df

    def _limit_iterator(self, session: Session, limit: int, step: int = 100):
        df = self._get_df_to_iterate()
        n = len(df)
        start_time = time.time()
        logger.info(f"Starting transfer of {n} [limit={limit}] rows")
        for i, row in enumerate(df.itertuples()):
            if limit > 0 and i >= limit:
                logger.info(f"Reached limit of {limit} rows. Stopping migration.")
                break

            if i and not i % step:
                logger.info(
                    f"Processing row {i} of {n},  avg rows per second: {step / (time.time() - start_time):.2f}"
                )
                start_time = time.time()
                try:
                    session.commit()
                    session.expunge_all()
                except Exception as e:
                    logger.critical(f"Error committing wells. {e}")
                    session.rollback()
                    continue

            self._step(session, df, i, row)

        session.commit()
        session.expunge_all()
        self._after_hook(session)

    def _step(self, session: Session, df: pd.DataFrame, i: int, row: dict):
        raise NotImplementedError("Must implement _iterator method")

    def _after_hook(self, session: Session):
        pass

    def _get_dfs(self):
        raise NotImplementedError("Must implement _get_dfs method")

    def _read_csv(self, name: str, dtype: dict | None = None, **kw) -> pd.DataFrame:
        if dtype is not None and "dtype" not in kw:
            kw["dtype"] = dtype
        csv_paths = self.flags.get("CSV_PATHS") or {}
        csv_path = csv_paths.get(name)
        if csv_path:
            return pd.read_csv(csv_path, **kw)
        return read_csv(name, dtype=dtype, **kw)

    def _dedupe_rows(
        self,
        rows: list[dict[str, Any]],
        key: str | list[str] = "nma_GlobalID",
        include_missing: bool = False,
    ) -> list[dict[str, Any]]:
        """Dedupe rows by unique key(s) to avoid ON CONFLICT loops. Later rows win."""
        deduped: dict[Any, dict[str, Any]] = {}
        passthrough: list[dict[str, Any]] = []
        key_list = key if isinstance(key, list) else [key]

        for row in rows:
            if len(key_list) == 1:
                row_key = row.get(key_list[0])
            else:
                row_key = tuple(row.get(k) for k in key_list)

            # Treat None and any pd.isna(...) value (e.g., NaN) as missing keys
            if isinstance(row_key, tuple):
                is_missing = any(pd.isna(k) for k in row_key)
            else:
                is_missing = pd.isna(row_key)

            if is_missing:
                if include_missing:
                    passthrough.append(row)
                continue

            deduped[row_key] = row

        if include_missing:
            return list(deduped.values()) + passthrough
        return list(deduped.values())


class ChunkTransferer(Transferer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chunk_size = 1000

    def _transfer_hook(self, session: Session):
        df = self._get_df_to_iterate()
        for ci, chunk in enumerate(chunk_by_size(df, self.chunk_size)):
            dbchunk = self._get_df_chunk(session, chunk)
            logger.info(
                f"Processing chunk {ci}, {len(chunk)} rows, {len(dbchunk)} db items"
            )
            for i, row in enumerate(chunk.itertuples()):
                dbitem = self._get_db_item(dbchunk, row)
                if not dbitem:
                    self._missing_db_item_warning(row)
                    continue
                self._chunk_step(session, df, i, row, dbitem)

            session.commit()
            session.expunge_all()

    # def chunk_transfer(self):
    #     with session_ctx() as session:
    #         self.input_df, self.cleaned_df = self._get_dfs(session)
    #         df = self._get_df_to_iterate()
    #         for ci, chunk in enumerate(chunk_by_size(df, self.chunk_size)):
    #             dbchunk = self._get_df_chunk(session, chunk)
    #             logger.info(
    #                 f"Processing chunk {ci}, {len(chunk)} rows, {len(dbchunk)} db items"
    #             )
    #             for i, row in enumerate(chunk.itertuples()):
    #                 dbitem = self._get_db_item(dbchunk, row)
    #                 if not dbitem:
    #                     self._missing_db_item_warning(row)
    #                     continue
    #                 self._chunk_iterator(session, df, i, row, dbitem)
    #         session.commit()

    def _get_df_chunk(self, session, chunk):
        raise NotImplementedError("Must be implemented in subclass")

    def _missing_db_item_warning(self, row):
        raise NotImplementedError("Must be implemented in subclass")

    def _chunk_step(self, session, df, i, row, dbitem):
        raise NotImplementedError("Must be implemented in subclass")

    def _get_db_item(self, chunk, row):
        raise NotImplementedError("Must be implemented in subclass")


class GroupTransferer(Transferer):
    def _get_group(self):
        return self.cleaned_df.groupby(["PointID"])

    def _transfer_hook(self, session: Session):
        self._group_iterator(session)

    def _group_iterator(self, session: Session):
        groups = self._get_group()
        for index, group in groups:
            db_item = self._get_db_item(session, index)
            if db_item is None:
                logger.warning(self._no_db_item_warning(index))
                continue

            prepped_group = self._get_prepped_group(group)
            self._pre_group_step(session, prepped_group, db_item)
            for row in prepped_group.itertuples():
                try:
                    self._group_step(session, row, db_item)
                except Exception as e:
                    import traceback

                    pointid = self._get_point_id(row, db_item)
                    traceback.print_exc()
                    logger.critical(f"Could not add sensor and deployment: {e}")
                    self._capture_error(pointid, e, "UnknownField")

    def _get_point_id(self, row: pd.Series, db_item: Base) -> str:
        return row.PointID

    def _pre_group_step(self, session: Session, group: DataFrame, db_item: Base):
        pass

    def _group_step(self, session: Session, row: pd.Series, db_item: Base):
        raise NotImplementedError("Must be implemented in subclass")

    def _get_prepped_group(self, group) -> DataFrame:
        raise NotImplementedError("Must be implemented in subclass")

    def _no_db_item_warning(self, index) -> str:
        raise NotImplementedError("Must be implemented in subclass")

    def _get_db_item(self, session, index) -> Thing:
        raise NotImplementedError("Must be implemented in subclass")


class ThingBasedTransferer(GroupTransferer):
    def _get_group(self):
        return self.cleaned_df.groupby(["PointID"])

    def _get_db_item(self, session, index) -> Thing:
        pointid = index[0]
        return session.query(Thing).filter(Thing.name == pointid).first()


class ChemistryTransferer(Transferer):
    def __init__(self, *args, batch_size: int = 1000, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        # Cache: legacy UUID -> Integer id
        self._sample_info_cache: dict[UUID, int] = {}
        self._build_sample_info_cache()
        self._parse_dates = None

    def _build_sample_info_cache(self) -> None:
        """Build cache of nma_sample_pt_id -> id for FK lookups."""
        with session_ctx() as session:
            sample_infos = (
                session.query(
                    NMA_Chemistry_SampleInfo.nma_sample_pt_id,
                    NMA_Chemistry_SampleInfo.id,
                )
                .filter(NMA_Chemistry_SampleInfo.nma_sample_pt_id.isnot(None))
                .all()
            )
            self._sample_info_cache = {
                nma_sample_pt_id: csi_id for nma_sample_pt_id, csi_id in sample_infos
            }
        logger.info(
            f"Built ChemistrySampleInfo cache with {len(self._sample_info_cache)} entries"
        )

    def _get_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        input_df = self._read_csv(self.source_table, parse_dates=self._parse_dates)
        cleaned_df = self._filter_to_valid_sample_infos(input_df)
        return input_df, cleaned_df

    def _filter_to_valid_sample_infos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter to only include rows where SamplePtID matches a ChemistrySampleInfo.

        This prevents orphan records and ensures the FK constraint will be satisfied.
        """
        valid_sample_pt_ids = set(self._sample_info_cache.keys())
        before_count = len(df)
        parsed_sample_pt_ids = df["SamplePtID"].map(self._uuid_val)
        mask = parsed_sample_pt_ids.isin(valid_sample_pt_ids)
        filtered_df = df[mask].copy()
        inverted_df = df[~mask].copy()
        if not inverted_df.empty:
            for _, row in inverted_df.iterrows():
                sample_pt_id = row.get("SamplePtID")
                self._capture_error(
                    sample_pt_id,
                    f"No matching ChemistrySampleInfo for SamplePtID: {sample_pt_id}",
                    "SamplePtID",
                )

        after_count = len(filtered_df)

        if before_count > after_count:
            skipped = before_count - after_count
            table_name = self.source_table or self.__class__.__name__
            logger.warning(
                f"Filtered out {skipped} {table_name} records without matching "
                f"ChemistrySampleInfo ({after_count} valid, {skipped} orphan records prevented)"
            )

        return filtered_df

    def _safe_str(self, row, attr: str) -> Optional[str]:
        """Safely get a string value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        return str(val)

    def _safe_float(self, row, attr: str) -> Optional[float]:
        """Safely get a float value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, row, attr: str) -> Optional[int]:
        """Safely get an int value, returning None for NaN."""
        val = getattr(row, attr, None)
        if val is None or pd.isna(val):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

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


# ============= EOF =============================================
