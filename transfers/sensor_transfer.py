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

from db import Sensor, Deployment, Thing
from transfers.util import read_csv, logger, filter_to_valid_point_ids, replace_nans

EQUIPMENT_TO_SENSOR_TYPE_MAP = {
    "Pressure transducer": "Pressure Transducer",
    "Acoustic sounder": "Acoustic Sounder",
    "Barometer": "Barometer",
}


def transfer_sensors(session):
    equipment = read_csv("Equipment")
    equipment.columns = equipment.columns.str.replace(" ", "_")
    equipment = equipment[equipment.SerialNo.notna()]
    equipment = filter_to_valid_point_ids(session, equipment)
    equipment = replace_nans(equipment)

    grouped_equipment = equipment.groupby(["PointID"])
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
                if row.EquipmentType not in EQUIPMENT_TO_SENSOR_TYPE_MAP:
                    logger.critical(
                        f"Skipping equipment with type {row.EquipmentType} for point {pointid}"
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
                    sensor = Sensor(
                        nma_pk_equipment=row.GlobalID,
                        name=row.ID,
                        sensor_type=EQUIPMENT_TO_SENSOR_TYPE_MAP[row.EquipmentType],
                        model=row.Model,
                        serial_no=row.SerialNo,
                        owner_agency="NMBGMR",
                        notes=row.Equipment_Notes,
                    )
                    session.add(sensor)
                    logger.info(
                        f"Added sensor {sensor.name} with serial number {sensor.serial_no}"
                    )

                installation_date = datetime.strptime(
                    row.DateInstalled, "%Y-%m-%d %H:%M:%S.%f"
                ).date()
                removal_date = (
                    datetime.strptime(row.DateRemoved, "%Y-%m-%d %H:%M:%S.%f").date()
                    if not pd.isna(row.DateRemoved)
                    else None
                )
                deployment = Deployment(
                    thing=thing,
                    sensor=sensor,
                    installation_date=installation_date,
                    removal_date=removal_date,
                    recording_interval=int(row.RecordingInterval),
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
