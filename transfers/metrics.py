from services.gcs_helper import get_storage_bucket

1  # ===============================================================================
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
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from db import (
    Thing,
    WellScreen,
    Sensor,
    Contact,
    Observation,
    Parameter,
    Deployment,
    TransducerObservation,
)


class Metrics:
    include_errors = True

    def __init__(self):
        # create a new path for the metrics
        root = Path("metrics")
        if not os.getcwd().endswith("transfers"):
            root = Path("transfers") / root

        if not os.path.exists(root):
            os.mkdir(root)

        self.path = root / f"metrics_{datetime.now().strftime('%Y-%m-%dT%H_%M_%S')}.csv"
        delimiter = "|" if self.include_errors else ","
        self._fileobj = self.path.open("w")
        self._writer = csv.writer(self._fileobj, delimiter=delimiter)
        self._writer.writerow(
            ["model", "input_count", "cleaned_count", "transferred", "issue_percentage"]
        )

    def save_to_storage_bucket(self):
        bucket = get_storage_bucket()
        log_filename = self.path.name
        blob = bucket.blob(f"transfer_metrics/{log_filename}")
        blob.upload_from_string(self.path.read_text())

    def close(self):
        self._fileobj.close()

    def well_metrics(self, *args, **kw) -> None:
        self._handle_metrics(
            Thing, where=Thing.thing_type == "water well", name="Well", *args, **kw
        )

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
        metrics = self._make_metrics(
            Contact.__name__, len(input_df) * 2, len(cleaned_df) * 2, count
        )
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

        metrics = self._make_metrics(
            "Manual Water Levels", len(input_df), len(cleaned_df), count
        )
        self._writer.writerow(metrics)
        self._write_errors(errors)

    def acoustic_metrics(self, *args, **kw) -> None:
        self._transducer_metrics("Acoustic Sounder", *args, **kw)

    def pressure_metrics(self, *args, **kw) -> None:
        self._transducer_metrics("Pressure Transducer", *args, **kw)

    def _transducer_metrics(
        self, sensor_type, sess, input_df, cleaned_df, errors
    ) -> None:
        sql = (
            select(func.count())
            .select_from(TransducerObservation)
            .join(Deployment)
            .join(Sensor)
            .join(Parameter)
            .where(Sensor.sensor_type == sensor_type)
            .where(Parameter.parameter_name == "groundwater level")
        )
        count = sess.execute(sql).scalar_one()
        metrics = self._make_metrics(sensor_type, len(input_df), len(cleaned_df), count)
        self._writer.writerow(metrics)
        self._write_errors(errors)

    def _make_metrics(self, name, input_n, cleaned_n, count):
        percent_issue = (cleaned_n - count) / cleaned_n * 100 if cleaned_n != 0 else 0
        return [name, input_n, cleaned_n, count, percent_issue]

    def _handle_metrics(
        self, model, sess, input_df, cleaned_df, errors, where=None, name=None
    ) -> None:
        count = self._get_count(sess, model, where=where)

        if name is None:
            name = model.__name__
        self._write_metrics(name, count, input_df, cleaned_df)
        self._write_errors(errors)

    def _write_errors(self, errors: list) -> None:
        if self.include_errors:
            self._writer.writerow(["PointID", "Table", "Field", "Error"])
            for record in errors:
                error = record["error"]
                # if not isinstance(error, (list, tuple)):
                #     error = [error]
                if isinstance(error, str):
                    error = [error]
                elif isinstance(error, ValidationError):
                    nes = []
                    for e in error.errors():
                        try:
                            nes.append(f"{e['loc'][0]}: {e['msg']}")
                        except IndexError:
                            nes.append(e["msg"])
                    error = nes
                elif isinstance(error, ProgrammingError):
                    detail = error.orig.args[0].get("D")
                    error = [detail]
                elif isinstance(error, Exception):
                    error = [str(error)]

                for ee in error:
                    self._writer.writerow(
                        [
                            record["pointid"],
                            record.get("table"),
                            record.get("field"),
                            ee,
                        ]
                    )

            self._writer.writerow([])

    def _write_metrics(
        self, name: str, count: int, input_df: DataFrame, cleaned_df: DataFrame
    ) -> None:
        metrics = self._make_metrics(name, len(input_df), len(cleaned_df), count)
        self._writer.writerow(metrics)

    def _get_count(self, sess: Session, model, where=None) -> int:
        sql = select(func.count()).select_from(model)
        if where:
            sql = sql.where(where)
        count = sess.execute(sql).scalar_one()
        return count


# ============= EOF =============================================
