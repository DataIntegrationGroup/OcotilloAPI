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

import pandas as pd
from pandas import Timestamp
from pydantic import ValidationError
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from db import Thing, Deployment, Sensor
from db.transducer import TransducerObservation, TransducerObservationBlock
from schemas.transducer import CreateTransducerObservation
from transfers.logger import logger
from transfers.transferer import Transferer
from transfers.util import (
    read_csv,
    filter_to_valid_point_ids,
    get_groundwater_parameter_id,
)


class WaterLevelsContinuousTransferer(Transferer):
    _partition_field: str
    _sensor_types: tuple[str]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.groundwater_parameter_id = get_groundwater_parameter_id()
        self._itertuples_field_map = {}
        self._df_columns = set()
        if self._sensor_types is None:
            raise ValueError("_sensor_types must be set")
        if self._partition_field is None:
            raise ValueError("_partition_field must be set")

    def _get_dfs(self):
        input_df = read_csv(self.source_table, parse_dates=["DateMeasured"])
        cleaned_df = filter_to_valid_point_ids(input_df)
        cleaned_df = cleaned_df.sort_values(by=["PointID"])

        # remove rows with no date measured
        cleaned_df = cleaned_df[cleaned_df.DateMeasured.notna()]

        # remove duplicate rows
        cleaned_df = cleaned_df.drop_duplicates(subset=["PointID", "DateMeasured"])

        self._df_columns = set(cleaned_df.columns)
        self._itertuples_field_map = self._build_itertuples_field_map(cleaned_df)

        return input_df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        gwd = self.cleaned_df.groupby(["PointID"])
        n = len(gwd)
        nodeployments = {}
        for i, (index, group) in enumerate(gwd):
            pointid = index[0]
            logger.info(
                f"Processing PointID: {pointid}. {i + 1}/{n} ({100*(i+1)/n:0.2f}) completed."
            )

            deployments = (
                session.query(Deployment)
                .join(Thing)
                .join(Sensor)
                .where(Sensor.sensor_type.in_(self._sensor_types))
                .where(Thing.name == pointid)
                .all()
            )

            # sort rows by date measured
            group = group.sort_values(by="DateMeasured")
            field = getattr(group, self._partition_field)

            qced = group[field == 1]
            notqced = group[~(field == 1)]

            # Check for deployments first to get thing_id
            if not deployments:
                logger.critical(
                    f"Thing with PointID={pointid} has no deployments. Skipping all water levels"
                )
                self._capture_error(pointid, "no deployments", "DateMeasured")
                continue

            # Get thing_id from the first deployment
            thing_id = deployments[0].thing_id

            qced_block = TransducerObservationBlock(
                thing_id=thing_id,
                parameter_id=self.groundwater_parameter_id,
                review_status="approved",
            )
            notqced_block = TransducerObservationBlock(
                thing_id=thing_id,
                parameter_id=self.groundwater_parameter_id,
                review_status="not reviewed",
            )

            for block, rows, release_status in (
                (qced_block, qced, "public"),
                (notqced_block, notqced, "private"),
            ):
                block.start_datetime = rows.DateMeasured.min()
                block.end_datetime = rows.DateMeasured.max()

                if rows.empty:
                    logger.info(f"no {release_status} records for pointid {pointid}")
                    continue

                deps_sorted = sorted(
                    deployments, key=lambda d: Timestamp(d.installation_date)
                )

                observations = [
                    self._make_observation(
                        pointid, row, release_status, deps_sorted, nodeployments
                    )
                    for row in rows.itertuples()
                ]

                observations = [obs for obs in observations if obs is not None]
                session.bulk_save_objects(observations)
                session.add(block)
                logger.info(
                    f"Added {len(observations)} water levels {release_status} block"
                )
                try:
                    session.commit()
                except DatabaseError as e:
                    session.rollback()
                    logger.critical(
                        f"Error committing water levels {release_status} block: {e}"
                    )
                    self._capture_database_error(pointid, e)
                    continue

        # convert nodeployments to errors
        for pointid, (min_date, max_date) in nodeployments.items():
            self._capture_error(
                pointid,
                "DateMeasured",
                f"no deployment between {min_date} and {max_date}",
            )

    def _make_observation(
        self,
        pointid: str,
        row: pd.Series,
        release_status: str,
        deps_sorted: list,
        nodeployments: dict,
    ) -> TransducerObservation | None:
        deployment = _find_deployment(row.DateMeasured, deps_sorted)

        if deployment is None:
            if pointid not in nodeployments:
                nodeployments[pointid] = (row.DateMeasured, row.DateMeasured)
            else:
                min_date, max_date = nodeployments[pointid]
                if row.DateMeasured < min_date:
                    min_date = row.DateMeasured
                elif row.DateMeasured > max_date:
                    max_date = row.DateMeasured
                nodeployments[pointid] = min_date, max_date

            logger.critical(
                f"No deployment found for PointID={pointid} at {row.DateMeasured}"
            )
            return None

        try:
            payload = dict(
                parameter_id=self.groundwater_parameter_id,
                deployment_id=deployment.id,
                observation_datetime=row.DateMeasured,
                value=row.DepthToWaterBGS,
                release_status=release_status,
            )
            obspayload = CreateTransducerObservation.model_validate(
                payload
            ).model_dump()
            legacy_payload = self._legacy_payload(row)
            return TransducerObservation(**obspayload, **legacy_payload)

        except ValidationError as e:
            logger.critical(f"Observation validation error: {e.errors()}")
            self._capture_error(pointid, str(e), "DepthToWaterBGS")

    def _legacy_payload(self, row: pd.Series) -> dict:
        def val(key: str):
            if key not in self._df_columns:
                return None
            field = self._itertuples_field_map.get(key, key)
            v = getattr(row, field, None)
            if pd.isna(v):
                return None
            return v

        return {
            "nma_waterlevelscontinuous_pressure_conddl_ms_cm": val("CONDDL (mS/cm)"),
            "nma_waterlevelscontinuous_pressure_checked_by": val("CheckedBy"),
            "nma_waterlevelscontinuous_pressure_created": val("Created"),
            "nma_waterlevelscontinuous_pressure_data_source": val("DataSource"),
            "nma_waterlevelscontinuous_pressure_global_id": val("GlobalID"),
            "nma_waterlevelscontinuous_pressure_measurement_method": val(
                "MeasurementMethod"
            ),
            "nma_waterlevelscontinuous_pressure_measuring_agency": val(
                "MeasuringAgency"
            ),
            "nma_waterlevelscontinuous_pressure_notes": val("Notes"),
            "nma_waterlevelscontinuous_pressure_processed_by": val("ProcessedBy"),
            "nma_waterlevelscontinuous_pressure_qced": val("QCed"),
            "nma_waterlevelscontinuous_pressure_temperature_water": val(
                "TemperatureWater"
            ),
            "nma_waterlevelscontinuous_pressure_updated": val("Updated"),
            "nma_waterlevelscontinuous_pressure_water_head": val("WaterHead"),
            "nma_waterlevelscontinuous_pressure_water_head_adjusted": val(
                "WaterHeadAdjusted"
            ),
        }

    @staticmethod
    def _build_itertuples_field_map(df: pd.DataFrame) -> dict[str, str]:
        """
        Map original column names to itertuples field names using pandas' rename logic.
        """
        mapping: dict[str, str] = {}
        iterator = df.itertuples()
        first_row = next(iterator, None)
        if first_row is None:
            return mapping

        fields = first_row._fields
        for idx, col in enumerate(df.columns):
            field = fields[idx + 1]
            if field != col:
                mapping[col] = field
        return mapping


class WaterLevelsContinuousPressureTransferer(WaterLevelsContinuousTransferer):
    source_table = "WaterLevelsContinuous_Pressure"
    _partition_field = "QCed"
    _sensor_types = ("Pressure Transducer", "Barometer", "DiverLink", "Diver Cable")


class WaterLevelsContinuousAcousticTransferer(WaterLevelsContinuousTransferer):
    source_table = "WaterLevelsContinuous_Acoustic"
    _partition_field = "PublicRelease"
    _sensor_types = ("Acoustic Sounder",)


def _find_deployment(ts, deployments):
    date = ts.date()
    for d in deployments:
        if d.installation_date > date:
            break  # because sorted by start
        end = d.removal_date if d.removal_date else Timestamp.max.date()
        if end >= date:
            return d
    return None


# ============= EOF =============================================
