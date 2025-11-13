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
from transfers.util import read_csv, logger, filter_to_valid_point_ids, replace_nans

EQUIPMENT_TO_SENSOR_TYPE_MAP = {
    "Pressure transducer": "Pressure Transducer",
    "Acoustic sounder": "Acoustic Sounder",
    "Barometer": "Barometer",
}


def transfer_sensors(session):
    source_table = "Equipment"
    input_df = read_csv(source_table)
    input_df.columns = input_df.columns.str.replace(" ", "_")
    input_df = input_df[input_df.SerialNo.notna()]
    cleaned_df = filter_to_valid_point_ids(session, input_df)
    cleaned_df = replace_nans(cleaned_df)
    errors = []
    grouped_equipment = cleaned_df.groupby(["PointID"])
    for index, group in grouped_equipment:
        pointid = index[0]
        thing = session.query(Thing).filter(Thing.name == pointid).first()
        if thing is None:
            logger.warning(
                f"Skipping sensor transfer for Thing with PointID {pointid} since it is not in the DB"
            )
            continue
        ordered_group = group.sort_values(by=["DateInstalled"])

        try:
            for row in ordered_group.itertuples():
                try:
                    sensor_type = EQUIPMENT_TO_SENSOR_TYPE_MAP[row.EquipmentType]
                except KeyError as e:
                    logger.critical(
                        f"Skipping equipment with type {row.EquipmentType} for point {pointid}"
                    )
                    error = (
                        f"key error adding sensor_type:{row.EquipmentType} error: {e}"
                    )
                    errors.append(
                        {
                            "pointid": pointid,
                            "error": error,
                            "table": source_table,
                            "field": "EquipmentType",
                        }
                    )
                    continue

                sensor = (
                    session.query(Sensor)
                    .filter(Sensor.serial_no == row.SerialNo)
                    .one_or_none()
                )
                if sensor:
                    logger.info(
                        f"Sensor with serial number {row.SerialNo} already exists. Only creating deployment for that record"
                    )
                else:

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
                    session.add(sensor)
                    logger.info(
                        f"Added sensor {sensor.name} with serial number {sensor.serial_no}"
                    )

                if row.DateInstalled:
                    installation_date = datetime.strptime(
                        row.DateInstalled, "%Y-%m-%d %H:%M:%S.%f"
                    ).date()
                else:
                    logger.critical(
                        f"Installation Date cannot be None. Skipping deployment. Sensor: {row.ID}, "
                        f"SerialNo: {row.SerialNo} PointID: {pointid}"
                    )
                    errors.append(
                        {
                            "pointid": pointid,
                            "error": f"row.ID={row.ID}, row.SerialNo={row.SerialNo}. Installation Date cannot "
                            f"be None",
                            "table": source_table,
                            "field": "DateInstalled",
                        }
                    )
                    continue

                removal_date = None
                if row.DateRemoved:
                    removal_date = datetime.strptime(
                        row.DateRemoved, "%Y-%m-%d %H:%M:%S.%f"
                    ).date()

                try:
                    recording_interval = int(row.RecordingInterval)
                except (ValueError, TypeError):
                    logger.critical(
                        f"name={sensor.name}, serial_no={sensor.serial_no} RecordingInterval is not an "
                        f"integer. Setting to None"
                    )
                    recording_interval = None
                    errors.append(
                        {
                            "pointid": pointid,
                            "error": f"row.ID={row.ID}, row.SerialNo={row.SerialNo}. RecordingInterval is "
                            f"not an integer",
                            "table": source_table,
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
                    continue

                # TODO: add validation
                deployment = Deployment(
                    thing=thing,
                    sensor=sensor,
                    installation_date=installation_date,
                    removal_date=removal_date,
                    recording_interval=recording_interval,
                    recording_interval_units="hour",
                    hanging_cable_length=row.HangingCableLength,
                    hanging_point_height=row.HangingPointHgt,
                    hanging_point_description=row.HangingPointDescription,
                )
                session.add(deployment)
                logger.info(
                    f"Added deployment for sensor with serial number {sensor.serial_no}, deployed to {thing.name}: | Installation Date: {installation_date} | Removal Date: {removal_date}"
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
            session.commit()
        except Exception as e:
            logger.critical(f"Could not add sensor and deployment: {e}")
            errors.append({"pointid": pointid, "error": e, "table": source_table})

    return input_df, cleaned_df, errors


# ============= EOF =============================================
def init_sensor(session):
    sensor = Sensor()
    sensor.name = "Groundwater level manual measurement"
    sensor.description = "manual gwl measurement. needs to be replaced with measurementmethod(?) e.g. steel tape, eprobe, etc."
    sensor.unit = "ft"
    sensor.datetime_installed = datetime.now()
    session.add(sensor)
    session.commit()


if __name__ == "__main__":
    transfer_sensors("abc")
