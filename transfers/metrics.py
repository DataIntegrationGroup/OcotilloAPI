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

from sqlalchemy import select, func

from db import Thing


class Metrics:
    def __init__(self):
        # create a new path for the metrics
        root = Path("metrics")
        if not os.getcwd().endswith("transfers"):
            root = Path("transfers") / root

        if not os.path.exists(root):
            os.mkdir(root)

        self.path = root / f"metrics_{datetime.now()}.csv"

        self._writer = csv.writer(self.path.open("a"), delimiter="|")
        self._write_metrics(["model", "transfered", "input_count", "cleaned_count"])

    def well_transfer_metrics(self, sess, input_df, cleaned_df, errors):
        # get the nunmber of wells in the database
        sql = (
            select(func.count())
            .select_from(Thing)
            .where(Thing.thing_type == "water well")
        )
        count = sess.execute(sql).scalar_one()
        metrics = ["Water well", count, len(input_df), len(cleaned_df)]
        self._write_metrics(metrics)
        self._write_errors(errors)

    def _write_errors(self, errors):
        self._writer.writerow(["PointID", "Error"])
        for e in errors:
            error = e["error"]
            if not isinstance(error, (list, tuple)):
                error = [error]

            for ee in error:
                self._writer.writerow([e["pointid"], ee])

    def _write_metrics(self, metrics):
        self._writer.writerow(metrics)


# ============= EOF =============================================
