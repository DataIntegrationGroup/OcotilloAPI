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
import csv
from collections import defaultdict
from io import StringIO
from typing import Any

import pandas as pd
from pandas import Timestamp
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from db import Thing, Deployment, Sensor
from db.transducer import TransducerObservation, TransducerObservationBlock
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
        self._deployment_lookup_chunk_size = int(
            self.flags.get("DEPLOYMENT_LOOKUP_CHUNK_SIZE", 2000)
        )
        self._copy_chunk_size = int(self.flags.get("COPY_CHUNK_SIZE", 10000))
        self._use_copy_insert = bool(self.flags.get("USE_COPY_INSERT", True))
        self._observation_columns = {
            column.key for column in TransducerObservation.__table__.columns
        }
        if self._sensor_types is None:
            raise ValueError("_sensor_types must be set")
        if self._partition_field is None:
            raise ValueError("_partition_field must be set")

    def _get_dfs(self):
        input_df = read_csv(self.source_table, parse_dates=["DateMeasured"])
        cleaned_df = filter_to_valid_point_ids(input_df, self.pointids)
        cleaned_df = cleaned_df.sort_values(by=["PointID"])

        # remove rows with no date measured
        cleaned_df = cleaned_df[cleaned_df.DateMeasured.notna()]

        # remove duplicate rows
        cleaned_df = cleaned_df.drop_duplicates(subset=["PointID", "DateMeasured"])

        self._df_columns = set(cleaned_df.columns)
        self._itertuples_field_map = self._build_itertuples_field_map(cleaned_df)

        return input_df, cleaned_df

    def _transfer_hook(self, session: Session) -> None:
        gwd = self.cleaned_df.groupby("PointID", sort=False)
        n = gwd.ngroups
        deployments_by_pointid = self._prefetch_deployments(session)
        nodeployments = {}
        for i, (pointid, group) in enumerate(gwd):
            logger.info(
                f"Processing PointID: {pointid}. {i + 1}/{n} ({100*(i+1)/n:0.2f}) completed."
            )

            deployments = deployments_by_pointid.get(pointid, [])

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
            deps_sorted = deployments

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
                if rows.empty:
                    logger.info(f"no {release_status} records for pointid {pointid}")
                    continue

                block.start_datetime = rows.DateMeasured.iloc[0]
                block.end_datetime = rows.DateMeasured.iloc[-1]
                if block.end_datetime <= block.start_datetime:
                    # DB check constraint requires end > start, even for singleton blocks.
                    block.end_datetime = block.start_datetime + pd.Timedelta(
                        microseconds=1
                    )
                deployment_matcher = _DeploymentMatcher(deps_sorted)

                observations = []
                for row in rows.itertuples():
                    obs = self._make_observation(
                        pointid,
                        row,
                        release_status,
                        deployment_matcher,
                        nodeployments,
                    )
                    if obs is None:
                        continue
                    observations.append(
                        {k: v for k, v in obs.items() if k in self._observation_columns}
                    )
                if observations:
                    self._insert_observations(session, observations)
                block = self._get_or_create_block(session, block)
                logger.info(
                    f"Added {len(observations)} water levels {release_status} block"
                )
            try:
                session.commit()
            except DatabaseError as e:
                session.rollback()
                logger.critical(f"Error committing water levels for {pointid}: {e}")
                self._capture_database_error(pointid, e)
                continue

        # convert nodeployments to errors
        for pointid, (min_date, max_date) in nodeployments.items():
            self._capture_error(
                pointid,
                f"no deployment between {min_date} and {max_date}",
                "DateMeasured",
            )

    def _prefetch_deployments(self, session: Session) -> dict[str, list[Deployment]]:
        pointids = self.cleaned_df["PointID"].dropna().unique().tolist()
        deployments_by_pointid: dict[str, list[Deployment]] = defaultdict(list)
        if not pointids:
            return {}

        for i in range(0, len(pointids), self._deployment_lookup_chunk_size):
            chunk = pointids[i : i + self._deployment_lookup_chunk_size]
            deployment_rows = (
                session.query(Thing.name, Deployment)
                .join(Deployment, Deployment.thing_id == Thing.id)
                .join(Sensor, Sensor.id == Deployment.sensor_id)
                .where(Thing.name.in_(chunk))
                .where(Sensor.sensor_type.in_(self._sensor_types))
                .all()
            )
            for pointid, deployment in deployment_rows:
                deployments_by_pointid[pointid].append(deployment)

        for pointid in deployments_by_pointid:
            deployments_by_pointid[pointid].sort(
                key=lambda deployment: _installation_timestamp(
                    deployment.installation_date
                )
            )
        return dict(deployments_by_pointid)

    def _make_observation(
        self,
        pointid: str,
        row: pd.Series,
        release_status: str,
        deployment_matcher: "_DeploymentMatcher",
        nodeployments: dict,
    ) -> dict | None:
        deployment = deployment_matcher.find(row.DateMeasured)

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
            if payload["value"] is None or pd.isna(payload["value"]):
                self._capture_error(
                    pointid,
                    "DepthToWaterBGS is NULL",
                    "DepthToWaterBGS",
                )
                return None
            payload["value"] = float(payload["value"])
            legacy_payload = self._legacy_payload(row)
            return {**payload, **legacy_payload}

        except (TypeError, ValueError) as e:
            logger.critical(f"Observation build error: {e}")
            self._capture_error(pointid, str(e), "DepthToWaterBGS")

    def _insert_observations(
        self, session: Session, observations: list[dict[str, Any]]
    ) -> None:
        if not observations:
            return

        if not self._use_copy_insert:
            raise RuntimeError(
                "USE_COPY_INSERT=False is not supported; transducer observations now require COPY inserts."
            )
        self._copy_insert_observations(session, observations)

    def _copy_insert_observations(
        self, session: Session, observations: list[dict[str, Any]]
    ) -> None:
        raw_connection = session.connection().connection
        cursor = raw_connection.cursor()
        table_name = TransducerObservation.__table__.name
        columns = [
            key for key in observations[0].keys() if key in self._observation_columns
        ]
        if not columns:
            return

        copy_sql = (
            f"COPY {table_name} ({', '.join(columns)}) "
            "FROM STDIN WITH (FORMAT csv, NULL '\\N')"
        )

        for i in range(0, len(observations), self._copy_chunk_size):
            chunk = observations[i : i + self._copy_chunk_size]
            stream = StringIO()
            writer = csv.writer(stream, lineterminator="\n")
            for row in chunk:
                writer.writerow([_copy_cell(row.get(column)) for column in columns])
            stream.seek(0)
            cursor.execute(copy_sql, stream=stream)

    def _legacy_payload(self, row: pd.Series) -> dict:
        return {}

    def _legacy_val(self, row: pd.Series, key: str) -> Any:
        if key not in self._df_columns:
            return None
        field = self._itertuples_field_map.get(key, key)
        v = getattr(row, field, None)
        if pd.isna(v):
            return None
        return v

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

    def _get_or_create_block(
        self, session: Session, block: TransducerObservationBlock
    ) -> TransducerObservationBlock:
        existing = (
            session.query(TransducerObservationBlock)
            .filter(
                TransducerObservationBlock.thing_id == block.thing_id,
                TransducerObservationBlock.parameter_id == block.parameter_id,
                TransducerObservationBlock.review_status == block.review_status,
                TransducerObservationBlock.start_datetime
                == Timestamp(block.start_datetime),
                TransducerObservationBlock.end_datetime
                == Timestamp(block.end_datetime),
            )
            .one_or_none()
        )
        if existing:
            existing.comment = block.comment or existing.comment
            existing.release_status = block.release_status or existing.release_status
            existing.reviewer_id = block.reviewer_id or existing.reviewer_id
            existing.created_by_name = block.created_by_name or existing.created_by_name
            existing.created_by_id = block.created_by_id or existing.created_by_id
            existing.updated_by_name = block.updated_by_name or existing.updated_by_name
            existing.updated_by_id = block.updated_by_id or existing.updated_by_id
            return existing

        session.add(block)
        return block


class WaterLevelsContinuousPressureTransferer(WaterLevelsContinuousTransferer):
    source_table = "WaterLevelsContinuous_Pressure"
    _partition_field = "QCed"
    _sensor_types = ("Pressure Transducer", "Barometer", "DiverLink", "Diver Cable")

    def _legacy_payload(self, row: pd.Series) -> dict:
        val = self._legacy_val
        return {
            "nma_waterlevelscontinuous_pressure_conddl_ms_cm": val(
                row, "CONDDL (mS/cm)"
            ),
            "nma_waterlevelscontinuous_pressure_checked_by": val(row, "CheckedBy"),
            "nma_waterlevelscontinuous_pressure_created": val(row, "Created"),
            "nma_waterlevelscontinuous_pressure_data_source": val(row, "DataSource"),
            "nma_waterlevelscontinuous_pressure_global_id": val(row, "GlobalID"),
            "nma_waterlevelscontinuous_pressure_measurement_method": val(
                row, "MeasurementMethod"
            ),
            "nma_waterlevelscontinuous_pressure_measuring_agency": val(
                row, "MeasuringAgency"
            ),
            "nma_waterlevelscontinuous_pressure_notes": val(row, "Notes"),
            "nma_waterlevelscontinuous_pressure_processed_by": val(row, "ProcessedBy"),
            "nma_waterlevelscontinuous_pressure_qced": val(row, "QCed"),
            "nma_waterlevelscontinuous_pressure_temperature_water": val(
                row, "TemperatureWater"
            ),
            "nma_waterlevelscontinuous_pressure_updated": val(row, "Updated"),
            "nma_waterlevelscontinuous_pressure_water_head": val(row, "WaterHead"),
            "nma_waterlevelscontinuous_pressure_water_head_adjusted": val(
                row, "WaterHeadAdjusted"
            ),
        }


class WaterLevelsContinuousAcousticTransferer(WaterLevelsContinuousTransferer):
    source_table = "WaterLevelsContinuous_Acoustic"
    _partition_field = "PublicRelease"
    _sensor_types = ("Acoustic Sounder",)

    def _legacy_payload(self, row: pd.Series) -> dict:
        val = self._legacy_val
        return {
            "nma_waterlevelscontinuous_acoustic_created": val(row, "Created"),
            "nma_waterlevelscontinuous_acoustic_data_source": val(row, "DataSource"),
            "nma_waterlevelscontinuous_acoustic_global_id": val(row, "GlobalID"),
            "nma_waterlevelscontinuous_acoustic_measurement_method": val(
                row, "MeasurementMethod"
            ),
            "nma_waterlevelscontinuous_acoustic_measuring_agency": val(
                row, "MeasuringAgency"
            ),
            "nma_waterlevelscontinuous_acoustic_notes": val(row, "Notes"),
            "nma_waterlevelscontinuous_acoustic_point_id": val(row, "PointID"),
            "nma_waterlevelscontinuous_acoustic_pre_process_data_field": val(
                row, "PreProcessDataField"
            ),
            "nma_waterlevelscontinuous_acoustic_public_release": val(
                row, "PublicRelease"
            ),
            "nma_waterlevelscontinuous_acoustic_sensor_hgt_above_mp": val(
                row, "SensorHgtAboveMP"
            ),
            "nma_waterlevelscontinuous_acoustic_serial_no": val(row, "SerialNo"),
            "nma_waterlevelscontinuous_acoustic_server_receipt_date": val(
                row, "ServerReceiptDate"
            ),
            "nma_waterlevelscontinuous_acoustic_speaker_to_mic_length": val(
                row, "SpeakerToMicLength"
            ),
            "nma_waterlevelscontinuous_acoustic_temperature_air": val(
                row, "TemperatureAir"
            ),
        }


def _installation_timestamp(value: Any) -> Timestamp:
    if value is None:
        return Timestamp.min
    if isinstance(value, Timestamp):
        return value
    if hasattr(value, "date"):
        return Timestamp(value)
    return Timestamp(pd.to_datetime(value, errors="coerce"))


def _copy_cell(value: Any) -> Any:
    if value is None:
        return r"\N"
    if isinstance(value, Timestamp):
        if pd.isna(value):
            return r"\N"
        return value.to_pydatetime().isoformat(sep=" ")
    try:
        if pd.isna(value):
            return r"\N"
    except TypeError:
        pass
    if isinstance(value, bool):
        return "t" if value else "f"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


class _DeploymentMatcher:
    """
    Cursor-based matcher for monotonic time-series rows.
    Assumes rows are processed in ascending DateMeasured order.
    """

    def __init__(self, deployments: list[Deployment]):
        self._deployments = deployments
        self._cursor = 0

    def find(self, ts: Any) -> Deployment | None:
        date = _to_date(ts)
        n = len(self._deployments)
        while self._cursor < n:
            deployment = self._deployments[self._cursor]
            start = deployment.installation_date or Timestamp.min.date()
            end = deployment.removal_date or Timestamp.max.date()
            if date < start:
                return None
            if date <= end:
                return deployment
            self._cursor += 1
        return None


def _to_date(ts: Any):
    if hasattr(ts, "date"):
        return ts.date()
    return pd.Timestamp(ts).date()


def _find_deployment(ts, deployments):
    date = _to_date(ts)
    for d in deployments:
        start = d.installation_date or Timestamp.min.date()
        if start > date:
            break  # because sorted by start
        end = d.removal_date if d.removal_date else Timestamp.max.date()
        if end >= date:
            return d
    return None


# ============= EOF =============================================
