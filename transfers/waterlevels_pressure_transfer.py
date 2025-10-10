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
from db import Parameter, Thing
from db.transducer import TransducerObservation
from transfers.logger import logger
from transfers.util import read_csv


def transfer_water_levels_pressure(session):
    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )

    wd = read_csv("WaterLevelsContinuous_Pressure")

    # group by pointid
    gwd = wd.groupby(["PointID"])
    start_time = time.time()
    for index, group in gwd:
        pointid = index[0]
        logger.info(f"Processing PointID: {pointid}")
        thing = session.query(Thing).where(Thing.name == pointid).first()
        if thing is None:
            logger.critical(
                f"Thing with PointID={pointid} not found. Skipping water levels"
            )
            continue

        observations = []
        for i, row in enumerate(group.itertuples()):
            if pd.isna(row.DateMeasured):
                continue

            # get the sensor that was installed at this time.
            # sensor_id = _get_sensor_by_date(session, pointid, row.DateMeasured)

            observations.append(
                {
                    "thing_id": thing.id,
                    # "sensor_id": sensor_id,
                    "parameter_id": groundwater_parameter_id,
                    "observation_datetime": row.DateMeasured,
                    "value": row.DepthToWaterBGS,
                    "release_status": "public" if row.QCed else "private",
                }
            )
        session.bulk_insert_mappings(TransducerObservation, observations)
        session.commit()


def _get_sensor_by_date(session, pointid, date):
    return 1


# ============= EOF =============================================
