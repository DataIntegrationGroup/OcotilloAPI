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
import csv
import os
from datetime import datetime
from pathlib import Path

from pandas import DataFrame
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import Thing, WellScreen, Sensor, Contact, Observation, Parameter


class Metrics:
    def __init__(self):
        # create a new path for the metrics
        root = Path("metrics")
        if not os.getcwd().endswith("transfers"):
            root = Path("transfers") / root

        if not os.path.exists(root):
            os.mkdir(root)

        self.path = root / f"metrics_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"

        self._writer = csv.writer(self.path.open("a"), delimiter="|")
        self._writer.writerow(["model", "transferred", "input_count", "cleaned_count"])

    def well_metrics(self, *args, **kw) -> None:
        self._handle_metrics(Thing, where=Thing.thing_type == "water well", *args, **kw)

    def sensor_metrics(self, *args, **kw) -> None:
        self._handle_metrics(Sensor, *args, **kw)

    def well_screen_metrics(self, *args, **kw) -> None:
        self._handle_metrics(WellScreen, *args, **kw)

    def contact_metrics(self, sess, input_df, cleaned_df, errors) -> None:
        count = self._get_count(
            sess,
            Contact,
        )

        # since each contact in nma contacts a primary and a secondary contact multiply the count by 2
        metrics = [Contact.__name__, len(input_df) * 2, len(cleaned_df) * 2, count]
        self._writer.writerow(metrics)
        self._write_errors(errors)

    def water_level_metrics(self, sess, input_df, cleaned_df, errors) -> None:
        sql = (
            select(func.count())
            .select_from(Observation)
            .join(Parameter)
            .where(Parameter.parameter_name == "groundwater level")
        )
        count = sess.execute(sql).scalar_one()

        metrics = ["Manual Water Levels", len(input_df), len(cleaned_df), count]
        self._writer.writerow(metrics)
        self._write_errors(errors)

    def _handle_metrics(
        self, model, sess, input_df, cleaned_df, errors, where=None
    ) -> None:
        count = self._get_count(sess, model, where=where)
        self._write_metrics(model.__name__, count, input_df, cleaned_df)
        self._write_errors(errors)

    def _write_errors(self, errors: list) -> None:
        self._writer.writerow(["PointID", "Error"])
        for e in errors:
            error = e["error"]
            if not isinstance(error, (list, tuple)):
                error = [error]

            for ee in error:
                self._writer.writerow([e["pointid"], ee])
        self._writer.writerow([])

    def _write_metrics(
        self, name: str, count: int, input_df: DataFrame, cleaned_df: DataFrame
    ) -> None:
        metrics = [name, len(input_df), len(cleaned_df), count]

        self._writer.writerow(metrics)

    def _get_count(self, sess: Session, model, where=None) -> int:
        sql = select(func.count()).select_from(model)
        if where:
            sql = sql.where(where)
        count = sess.execute(sql).scalar_one()
        return count


# ============= EOF =============================================
