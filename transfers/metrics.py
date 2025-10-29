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

        self.path = root / f"metrics_{datetime.now()}.csv"
        self._write_metrics("model,transfered,input_count,cleaned_count")

    def well_transfer_metrics(self, sess, input_df, cleaned_df):
        # get the nunmber of wells in the database
        sql = (
            select(func.count())
            .select_from(Thing)
            .where(Thing.thing_type == "water well")
        )
        count = sess.execute(sql).scalar_one()
        metrics = f"Water well,{count},{len(input_df)},{len(cleaned_df)}"
        self._write_metrics(metrics)

    def _write_metrics(self, metrics):
        with open(self.path, "a") as f:
            f.write(f"{metrics}\n")


# ============= EOF =============================================
