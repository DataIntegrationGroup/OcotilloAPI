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

from sqlalchemy import select

from db import Sensor, Deployment, Thing
from transfers.transferer import ThingBasedTransferer
from transfers.util import (
    read_csv,
    logger,
    filter_to_valid_point_ids,
    replace_nans,
    RecordingIntervalEstimator,
)

EQUIPMENT_TO_SENSOR_TYPE_MAP = {
    "Pressure transducer": "Pressure Transducer",
    "Acoustic sounder": "Acoustic Sounder",
    "Barometer": "Barometer",
}


class SensorTransferer(ThingBasedTransferer):
    source_table = "Equipment"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._estimators = {}
        self._added = {}

    def _get_dfs(self, session):
        input_df = read_csv(self.source_table)
        input_df.columns = input_df.columns.str.replace(" ", "_")
        input_df = input_df[input_df.SerialNo.notna()]
        cleaned_df = filter_to_valid_point_ids(session, input_df)
        cleaned_df = replace_nans(cleaned_df)
        return input_df, cleaned_df

    def _no_db_item_warning(self, index):
        return f"Skipping sensor transfer for Thing with PointID {index[0]} since it is not in the DB"

    def _get_prepped_group(self, group):
        return group.sort_values(by=["DateInstalled"])

    def _step(self, session, row, db_item):
        pointid = self._get_point_id(row, db_item)

        try:
            sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP[row.EquipmentType]
        except KeyError as e:
            logger.critical(
                f"Skipping equipment with type {row.EquipmentType} for point {pointid}"
            )
            error = f"key error adding sensor_type:{row.EquipmentType} error: {e}"
            self.errors.append(
                {
                    "pointid": pointid,
                    "error": error,
                    "table": self.source_table,
                    "field": "EquipmentType",
                }
            )
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
            pointid = self._get_point_id(row)
            logger.critical(
                f"Installation Date cannot be None. Skipping deployment. Sensor: {row.ID}, "
                f"SerialNo: {row.SerialNo} PointID: {pointid}"
            )
            self.errors.append(
                {
                    "pointid": pointid,
                    "error": f"row.ID={row.ID}, row.SerialNo={row.SerialNo}. Installation Date cannot "
                    f"be None",
                    "table": self.source_table,
                    "field": "DateInstalled",
                }
            )
            return

        removal_date = None
        if row.DateRemoved:
            removal_date = datetime.strptime(
                row.DateRemoved, "%Y-%m-%d %H:%M:%S.%f"
            ).date()

        recording_interval_unit = "hour"
        try:
            recording_interval = int(row.RecordingInterval)
        except (ValueError, TypeError):
            # try to calculate recording interval from measurements
            if sensor_type in self._estimators:
                estimator = self._estimators[sensor_type]
            else:
                estimator = RecordingIntervalEstimator(sensor_type)
                self._estimators[sensor_type] = estimator

            recording_interval, unit, error = estimator.estimate_recording_interval(
                row, installation_date, removal_date
            )

            if recording_interval:
                recording_interval_unit = unit
                logger.info(
                    f"name={sensor.name}, serial_no={sensor.serial_no}. "
                    f"estimated recording interval: {recording_interval} {unit}"
                )
            else:
                logger.critical(
                    f"name={sensor.name}, serial_no={sensor.serial_no} error={error}"
                )

                self.errors.append(
                    {
                        "pointid": pointid,
                        "error": f"name={sensor.name}, row.SerialNo={row.SerialNo}. error={error}",
                        "table": self.source_table,
                        "field": "RecordingInterval",
                    }
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


# def transfer_sensors(session):
#     source_table = "Equipment"
#     input_df = read_csv(source_table)
#     input_df.columns = input_df.columns.str.replace(" ", "_")
#     input_df = input_df[input_df.SerialNo.notna()]
#     cleaned_df = filter_to_valid_point_ids(session, input_df)
#     cleaned_df = replace_nans(cleaned_df)
#     errors = []
#     grouped_equipment = cleaned_df.groupby(["PointID"])
#     added = {}
#     estimators = {}
#     for index, group in grouped_equipment:
#         pointid = index[0]
#         thing = session.query(Thing).filter(Thing.name == pointid).first()
#         if thing is None:
#             logger.warning(
#                 f"Skipping sensor transfer for Thing with PointID {pointid} since it is not in the DB"
#             )
#             continue
#         ordered_group = group.sort_values(by=["DateInstalled"])
#
#         try:
#             for row in ordered_group.itertuples():
#                 try:
#                     sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP[row.EquipmentType]
#                 except KeyError as e:
#                     logger.critical(
#                         f"Skipping equipment with type {row.EquipmentType} for point {pointid}"
#                     )
#                     error = (
#                         f"key error adding sensor_type:{row.EquipmentType} error: {e}"
#                     )
#                     errors.append(
#                         {
#                             "pointid": pointid,
#                             "error": error,
#                             "table": source_table,
#                             "field": "EquipmentType",
#                         }
#                     )
#                     continue
#
#                 if row.SerialNo in added:
#                     logger.info(
#                         f"Sensor with serial number {row.SerialNo} already added in this transfer session. Only creating deployment for that record"
#                     )
#                     sensor = added[row.SerialNo]
#                 else:
#                     sensor = (
#                         session.query(Sensor)
#                         .filter(Sensor.serial_no == row.SerialNo)
#                         .one_or_none()
#                     )
#                     if sensor:
#                         logger.info(
#                             f"Sensor with serial number {row.SerialNo} already exists. Only creating deployment for that record"
#                         )
#
#                 if not sensor:
#                     # TODO: Add validation
#                     sensor = Sensor(
#                         nma_pk_equipment=row.GlobalID,
#                         name=row.ID,
#                         sensor_type=sensor_type,
#                         model=row.Model,
#                         serial_no=row.SerialNo,
#                         owner_agency="NMBGMR",
#                         notes=row.Equipment_Notes,
#                     )
#                     added[row.SerialNo] = sensor
#                     session.add(sensor)
#                     logger.info(
#                         f"Added sensor {sensor.name} with serial number {sensor.serial_no}"
#                     )
#
#                 if row.DateInstalled:
#                     installation_date = datetime.strptime(
#                         row.DateInstalled, "%Y-%m-%d %H:%M:%S.%f"
#                     ).date()
#                 else:
#                     logger.critical(
#                         f"Installation Date cannot be None. Skipping deployment. Sensor: {row.ID}, "
#                         f"SerialNo: {row.SerialNo} PointID: {pointid}"
#                     )
#                     errors.append(
#                         {
#                             "pointid": pointid,
#                             "error": f"row.ID={row.ID}, row.SerialNo={row.SerialNo}. Installation Date cannot "
#                             f"be None",
#                             "table": source_table,
#                             "field": "DateInstalled",
#                         }
#                     )
#                     continue
#
#                 removal_date = None
#                 if row.DateRemoved:
#                     removal_date = datetime.strptime(
#                         row.DateRemoved, "%Y-%m-%d %H:%M:%S.%f"
#                     ).date()
#
#                 recording_interval_unit = "hour"
#                 try:
#                     recording_interval = int(row.RecordingInterval)
#                 except (ValueError, TypeError):
#                     error = "RecordingInterval is not an integer"
#                     # try to calculate recording interval from measurements
#                     if sensor_type in estimators:
#                         estimator = estimators[sensor_type]
#                     else:
#                         estimator = RecordingIntervalEstimator(sensor_type)
#                         estimators[sensor_type] = estimator
#
#                     recording_interval, unit, error = (
#                         estimator.estimate_recording_interval(
#                             row, installation_date, removal_date
#                         )
#                     )
#
#                     if recording_interval:
#                         recording_interval_unit = unit
#                         logger.info(
#                             f"name={sensor.name}, serial_no={sensor.serial_no}. "
#                             f"estimated recording interval: {recording_interval} {unit}"
#                         )
#                     else:
#                         logger.critical(
#                             f"name={sensor.name}, serial_no={sensor.serial_no} error={error}"
#                         )
#                         errors.append(
#                             {
#                                 "pointid": pointid,
#                                 "error": f"name={sensor.name}, row.SerialNo={row.SerialNo}. error={error}",
#                                 "table": source_table,
#                                 "field": "RecordingInterval",
#                             }
#                         )
#                 sql = (
#                     select(Deployment)
#                     .join(Thing)
#                     .join(Sensor)
#                     .where(Thing.name == pointid)
#                     .where(Sensor.serial_no == sensor.serial_no)
#                     .where(Deployment.installation_date == installation_date)
#                     .where(Deployment.removal_date == removal_date)
#                 )
#
#                 existing_deployment = session.execute(sql).scalars().one_or_none()
#                 if existing_deployment:
#                     logger.info("existing deployment")
#                     continue
#
#                 # TODO: add validation
#                 deployment = Deployment(
#                     thing=thing,
#                     sensor=sensor,
#                     installation_date=installation_date,
#                     removal_date=removal_date,
#                     recording_interval=recording_interval,
#                     recording_interval_units=recording_interval_unit,
#                     hanging_cable_length=row.HangingCableLength,
#                     hanging_point_height=row.HangingPointHgt,
#                     hanging_point_description=row.HangingPointDescription,
#                 )
#                 session.add(deployment)
#                 logger.info(
#                     f"Added deployment for sensor with serial number {sensor.serial_no}, deployed to {thing.name}: | Installation Date: {installation_date} | Removal Date: {removal_date}"
#                 )
#
#                 """
#                 Developer's notes
#
#                 Since it's unclear beforehand if a sensor has been removed just update
#                 the sensor_status based off of each deployments installation/removal
#                 dates
#                 """
#                 if installation_date:
#                     sensor.sensor_status = "In Service"
#                 if removal_date:
#                     sensor.sensor_status = "Retired"
#             session.commit()
#         except Exception as e:
#             import traceback
#
#             traceback.print_exc()
#             logger.critical(f"Could not add sensor and deployment: {e}")
#             errors.append({"pointid": pointid, "error": e, "table": source_table})
#
#     return input_df, cleaned_df, errors


# ============= EOF =============================================
