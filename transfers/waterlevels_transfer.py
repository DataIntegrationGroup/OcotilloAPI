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
import uuid
from datetime import datetime

import pandas as pd

from db import Thing, Sample, Observation
from transfers.util import filter_to_valid_point_ids, log, read_csv


def transfer_water_levels(session):

    wd = read_csv("WaterLevels")
    wd = filter_to_valid_point_ids(session, wd)
    gwd = wd.groupby(["PointID"])

    for index, group in gwd:
        for row in group.itertuples():
            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                log(row, f"Skipping row {row.Index} due to missing data.")
                continue

            dt = datetime.fromisoformat(row.DateMeasured)
            thing = session.query(Thing).where(Thing.name == row.PointID).first()
            if thing is None:
                log(
                    row,
                    f"Thing with PointID {row.PointID} not found. Skipping water level.",
                )
                continue

            sample = Sample()
            sample.sampler_name = "unknown"
            sample.sample_type = "groundwater level"

            sample.field_sample_id = str(uuid.uuid4())
            sample.sample_date = dt
            sample.thing = thing
            session.add(sample)

            obs = Observation()

            # TODO: this needs to be resolved
            obs.sensor_id = 1

            # TODO: this needs to be implemented
            # obs.nma_pk_observation = row.GlobalID

            obs.sample = sample
            obs.observation_datetime = dt
            obs.value = row.DepthToWater
            obs.measuring_point_height = row.MPHeight
            obs.observed_property = "groundwater level:groundwater level"
            obs.unit = "ft"

            session.add(obs)
            session.commit()


# ============= EOF =============================================
