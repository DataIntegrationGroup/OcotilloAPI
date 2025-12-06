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

import pandas as pd
from pandas import DataFrame
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from db import Thing, Base
from db.engine import session_ctx
from transfers.logger import logger
from transfers.util import chunk_by_size


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

    def transfer(self) -> None:
        with session_ctx() as session:
            self.input_df, self.cleaned_df = self._get_dfs()
            self._transfer_hook(session)
            session.commit()

    def _capture_validation_error(self, pointid: str, err: ValidationError) -> None:
        logger.critical(f"Validation Error: PointID={pointid}, {err}")
        self._capture_error(pointid, str(err.errors()), "UnknownField")

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
            if limit and i >= limit:
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


# ============= EOF =============================================
