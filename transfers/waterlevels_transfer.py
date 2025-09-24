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

from db import Thing, Sample, Observation, FieldEvent, FieldActivity
from transfers.util import (
    filter_to_valid_point_ids,
    logger,
    read_csv,
    convert_mt_to_utc,
    filter_by_valid_measuring_agency,
    lu_to_lexicon_map,
)


def transfer_water_levels(session):

    wd = read_csv("WaterLevels")
    wd = filter_to_valid_point_ids(session, wd)
    wd = filter_by_valid_measuring_agency(wd)
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

        n = len(group)
        for i, row in enumerate(group.itertuples()):
            if i and not i % 25:
                logger.info(
                    f"Processing row {i} of {n}. {row.PointID},  avg rows per second: {i / (time.time() - start_time):.2f}"
                )
                session.commit()

            if pd.isna(row.DepthToWater) or pd.isna(row.DateMeasured):
                logger.critical(f"Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to missing "
                                f"data.")
                continue

            if not pd.isna(row.TimeMeasured):
                dt_measured = f"{row.DateMeasured} {row.TimeMeasured}"
            else:
                dt_measured = f"{row.DateMeasured} 12:00:00 AM"

            try:
                dt = datetime.strptime(dt_measured, "%Y-%m-%d %I:%M:%S %p")
                dt_utc = convert_mt_to_utc(dt)
            except ValueError as e:
                logger.warning(
                    f"Skipping row PointID={row.PointID}, objectid={row.OBJECTID} due to invalid date/time: {e}"
                )
                continue

            release_status = "public" if row.PublicRelease else "private"

            """
            Developer's notes

            Assumes for manual water levels that the date/time of the water level
            measurement is the same as the date/time of the field event.
            """

            # if pd.isna(row.MeasuringAgency):
            #     collecting_organization = "Unknown"
            # else:
            #     collecting_organization = row.MeasuringAgency

            # if pd.isna(row.MeasuredBy):
            #     sampler_name = "Unknown"
            # else:
            #     sampler_name = row.MeasuredBy

            field_event = FieldEvent(
                thing=thing,
                event_date=dt_utc,
                # collecting_organization=collecting_organization,
                release_status=release_status,
            )

            session.add(field_event)

            field_activity = FieldActivity(
                field_event=field_event,
                activity_type="groundwater level",
                release_status=release_status,
            )
            session.add(field_activity)

            if not pd.isna(row.MeasurementMethod):
                sample_method = lu_to_lexicon_map[
                    f"LU_MeasurementMethod:{row.MeasurementMethod}"
                ]
            else:
                sample_method = "null placeholder"

            #todo: use create schema to validate data
            sample = Sample(
                field_activity=field_activity,
                # sampler_name=sampler_name,
                sample_date=dt_utc,
                sample_matrix="water",
                sample_name=str(
                    uuid.uuid4()
                ),  # TODO: should this stay as-is for water levels? since there are no lab-assigned names
                sample_method=sample_method,
                qc_type="Normal",
                depth_top=None,
                depth_bottom=None,
            )
            session.add(sample)

            # TODO: update for auto-collectors in the Sensor table, like e-probes
            #       update the deployment table here
            sensor_id = None

            if not pd.isna(row.LevelStatus):
                level_status = lu_to_lexicon_map[f"LU_LevelStatus:{row.LevelStatus}"]
            else:
                level_status = None

            # TODO: use create schema to validate data
            observation = Observation(
                sensor_id=sensor_id,
                sample=sample,
                nma_pk_waterlevels=row.GlobalID,
                value=row.DepthToWater,
                measuring_point_height=row.MPHeight,
                observed_property="groundwater level",
                unit="ft",
                level_status=level_status,
                observation_datetime=dt_utc,
            )

            session.add(observation)
        session.commit()


# ============= EOF =============================================
