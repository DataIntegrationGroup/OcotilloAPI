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
from datetime import datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import Sensor, Deployment, Thing, Base
from transfers.transferer import ThingBasedTransferer
from transfers.util import (
    read_csv,
    logger,
    filter_to_valid_point_ids,
    replace_nans,
    SensorParameterEstimator,
)

EQUIPMENT_TO_SENSOR_TYPE_MAP = {
    # Hydrological sensors
    "Pressure transducer": "Pressure Transducer",
    "Acoustic sounder": "Acoustic Sounder",
    "Barometer": "Barometer",
    "DiverLink": "DiverLink",
    "Diver Cable": "Diver Cable",
    # Meteorological/environmental sensors
    "Precip Collector": "Precip Collector",
    "Soil Moisture": "Soil Moisture Sensor",
    "Weather Station": "Weather Station",
    "Camera": "Camera",
    "Weir": "Weir",
    "Snow Lysimeter": "Snow Lysimeter",
    "Tipping Bucket": "Tipping Bucket",
    "Lysimeter": "Lysimeter",
}


def _coerce_wi_int(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_wi_mic_gain(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        value = value.strip()
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return bool(int(float(value)))
    except (TypeError, ValueError):
        return None


class SensorTransferer(ThingBasedTransferer):
    source_table = "Equipment"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estimators = {}
        self._added = {}

    def _get_dfs(self):
        input_df = read_csv(self.source_table)
        input_df.columns = input_df.columns.str.replace(" ", "_")
        input_df = input_df[input_df.SerialNo.notna()]
        cleaned_df = filter_to_valid_point_ids(input_df)
        cleaned_df = replace_nans(cleaned_df)
        return input_df, cleaned_df

    def _no_db_item_warning(self, index):
        return f"Skipping sensor transfer for Thing with PointID {index[0]} since it is not in the DB"

    def _get_prepped_group(self, group):
        return group.sort_values(by=["DateInstalled"])

    def _get_estimator(self, sensor_type):
        if sensor_type in self._estimators:
            estimator = self._estimators[sensor_type]
        else:
            estimator = SensorParameterEstimator(sensor_type)
            self._estimators[sensor_type] = estimator
        return estimator

    def _group_step(self, session: Session, row: pd.Series, db_item: Base):
        pointid = self._get_point_id(row, db_item)

        try:
            sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP[row.EquipmentType]
        except KeyError as e:
            logger.critical(
                f"Skipping equipment with type {row.EquipmentType} for point {pointid}"
            )
            error = f"key error adding sensor_type:{row.EquipmentType} error: {e}"
            self._capture_error(pointid, error, "EquipmentType")

            return

        if row.SerialNo in self._added:
            logger.info(
                f"Sensor with serial number {row.SerialNo} already added in this transfer session. Only creating deployment for that record"
            )
            sensor = self._added[row.SerialNo]
        else:
            sensor = (
                session.query(Sensor)
                .filter(Sensor.serial_no == row.SerialNo)
                .one_or_none()
            )
            if sensor:
                logger.info(
                    f"Sensor with serial number {row.SerialNo} already exists. Only creating deployment for that record"
                )

        if not sensor:
            # TODO: Add validation
            sensor = Sensor(
                nma_pk_equipment=row.GlobalID,
                name=row.ID,
                sensor_type=sensor_type,
                model=row.Model,
                serial_no=row.SerialNo,
                owner_agency="NMBGMR",
                notes=row.Equipment_Notes,
            )
            self._added[row.SerialNo] = sensor
            session.add(sensor)
            logger.info(
                f"Added sensor {sensor.name} with serial number {sensor.serial_no}"
            )

        if row.DateInstalled:
            installation_date = datetime.strptime(
                row.DateInstalled, "%Y-%m-%d %H:%M:%S.%f"
            ).date()
        else:
            pointid = self._get_point_id(row, None)
            estimator = self._get_estimator(sensor_type)
            installation_date = estimator.estimate_installation_date(row)
            if not installation_date:
                logger.critical(
                    f"Installation Date cannot be None. Skipping deployment. Sensor: {row.ID}, "
                    f"SerialNo: {row.SerialNo} PointID: {pointid}"
                )
                self._capture_error(
                    pointid,
                    f"row.SerialNo={row.SerialNo}. Installation Date cannot be None",
                    "DateInstalled",
                )
                return
            else:
                logger.warning(
                    f"Estimated installation date={installation_date} for {pointid}"
                )
                self._capture_error(
                    pointid,
                    f"Estimated installation date={installation_date}. Is this correct?",
                    "DateInstalled",
                )

        removal_date = None
        if row.DateRemoved:
            removal_date = datetime.strptime(
                row.DateRemoved, "%Y-%m-%d %H:%M:%S.%f"
            ).date()

        recording_interval_unit = "hour"
        try:
            recording_interval = int(row.RecordingInterval)
        except (ValueError, TypeError) as e:
            # try to calculate recording interval from measurements
            estimator = self._get_estimator(sensor_type)
            recording_interval, unit, error = estimator.estimate_recording_interval(
                row, installation_date, removal_date
            )

            if recording_interval is None:
                recording_interval_unit = unit
                logger.info(
                    f"name={sensor.name}, serial_no={sensor.serial_no}. "
                    f"estimated recording interval: {recording_interval} {unit}"
                )
                self._capture_error(
                    pointid,
                    f"Estimated recording interval={recording_interval} {unit}. Is this correct?",
                    "RecordingInterval",
                )

            else:
                logger.critical(
                    f"name={sensor.name}, serial_no={sensor.serial_no} error={error}"
                )

                self._capture_error(
                    pointid,
                    f"name={sensor.name}, row.SerialNo={row.SerialNo}. "
                    f"error=Could not estimate recording interval. estimator error: {error}",
                    "RecordingInterval",
                )

        sql = (
            select(Deployment)
            .join(Thing)
            .join(Sensor)
            .where(Thing.name == pointid)
            .where(Sensor.serial_no == sensor.serial_no)
            .where(Deployment.installation_date == installation_date)
            .where(Deployment.removal_date == removal_date)
        )

        existing_deployment = session.execute(sql).scalars().one_or_none()
        if existing_deployment:
            logger.info("existing deployment")
            return

        # TODO: add validation
        deployment = Deployment(
            thing=db_item,
            sensor=sensor,
            installation_date=installation_date,
            removal_date=removal_date,
            recording_interval=recording_interval,
            recording_interval_units=recording_interval_unit,
            hanging_cable_length=row.HangingCableLength,
            hanging_point_height=row.HangingPointHgt,
            hanging_point_description=row.HangingPointDescription,
            nma_WI_Duration=_coerce_wi_int(row.WI_Duration),
            nma_WI_EndFrequency=_coerce_wi_int(row.WI_EndFrequency),
            nma_WI_Magnitude=_coerce_wi_int(row.WI_Magnitude),
            nma_WI_MicGain=_coerce_wi_mic_gain(row.WI_MicGain),
            nma_WI_MinSoundDepth=_coerce_wi_int(row.WI_MinSoundDepth),
            nma_WI_StartFrequency=_coerce_wi_int(row.WI_StartFrequency),
        )
        session.add(deployment)
        logger.info(
            f"Added deployment for sensor with serial number {sensor.serial_no}, deployed to {db_item.name}: | "
            f"Installation Date: {installation_date} | Removal Date: {removal_date}"
        )

        """
        Developer's notes

        Since it's unclear beforehand if a sensor has been removed just update
        the sensor_status based off of each deployments installation/removal
        dates
        """
        if installation_date:
            sensor.sensor_status = "In Service"
        if removal_date:
            sensor.sensor_status = "Retired"


# ============= EOF =============================================
