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
import uuid
from datetime import datetime

import pandas as pd

from db import Thing, Sample, Observation
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    read_csv,
    convert_mt_to_utc,
)


def transfer_water_levels(session):

    wd = read_csv("WaterLevels")
    wd = filter_to_valid_point_ids(session, wd)
    gwd = wd.groupby(["PointID"])

    start_time = time.time()
    for index, group in gwd:
        logger.info(f"Processing PointID: {index[0]}")
        n = len(group)
        for i, row in enumerate(group.itertuples()):
            if i and not i % 25:
                logger.info(
                    f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
                )
                session.commit()

            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                logger.warning(f"Skipping row {row.Index} due to missing data.")
                continue

            if not pd.isna(row.TimeMeasured):
                dt_measured = f"{row.DateMeasured} {row.TimeMeasured}"
            else:
                dt_measured = f"{row.DateMeasured} 12:00:00 AM"

            dt = datetime.strptime(dt_measured, "%Y-%m-%d %I:%M:%S %p")
            dt_utc = convert_mt_to_utc(dt)

            thing = session.query(Thing).where(Thing.name == row.PointID).first()
            if thing is None:
                logger.warning(
                    f"Thing with PointID {row.PointID} not found. Skipping water level."
                )
                continue

            sample = Sample()
            sample.sampler_name = "unknown"
            sample.sample_type = "groundwater level"

            sample.field_sample_id = str(uuid.uuid4())
            sample.sample_date = dt_utc
            sample.thing = thing
            session.add(sample)

            obs = Observation()

            # TODO: this needs to be resolved
            obs.sensor_id = 1

            obs.nma_pk_waterlevels = row.GlobalID

            obs.sample = sample
            obs.observation_datetime = dt_utc
            obs.value = row.DepthToWater
            obs.measuring_point_height = row.MPHeight
            obs.observed_property = "groundwater level:groundwater level"
            obs.unit = "ft"

            session.add(obs)
        session.commit()


# ============= EOF =============================================
