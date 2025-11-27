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
from pandas import to_datetime, Timestamp
from pydantic import ValidationError

from db import Parameter, Thing, Deployment, Sensor
from db.transducer import TransducerObservation, TransducerObservationBlock
from transfers.logger import logger
from transfers.util import read_csv, filter_to_valid_point_ids


def transfer_water_levels_acoustic(session):
    source_table = "WaterLevelsContinuous_Acoustic"
    wd = read_csv(source_table)
    return _transfer_water_levels_continuous(
        session, source_table, wd, "PublicRelease", "Acoustic Sounder"
    )


def transfer_water_levels_pressure(session):
    source_table = "WaterLevelsContinuous_Pressure"
    wd = read_csv(source_table)
    return _transfer_water_levels_continuous(
        session, source_table, wd, "QCed", "Pressure Transducer"
    )


def _find_deployment(ts, deployments):
    for d in deployments:
        start = Timestamp(d.installation_date)
        if start > ts:
            break  # because sorted by start
        end = Timestamp(d.removal_date) if d.removal_date else Timestamp.max
        if end >= ts:
            return d
    return None


def _transfer_water_levels_continuous(
    session, source_table, input_df, partition_field, sensor_type
):
    from schemas.transducer import CreateTransducerObservation

    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )
    cleaned_df = filter_to_valid_point_ids(session, input_df)

    # group by pointid
    cleaned_df = cleaned_df.sort_values(by=["PointID"])
    gwd = cleaned_df.groupby(["PointID"])
    n = len(gwd)
    errors = []
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
            .where(Sensor.sensor_type == sensor_type)
            .where(Thing.name == pointid)
            .all()
        )

        # remove rows with no date measured
        group = group[group.DateMeasured.notna()]
        group["DateMeasured"] = to_datetime(group["DateMeasured"], errors="coerce")

        # sort rows by date measured
        group = group.sort_values(by="DateMeasured")
        field = getattr(group, partition_field)

        qced = group[field == 1]
        notqced = group[~(field == 1)]

        qced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, review_status="approved"
        )
        notqced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, review_status="not reviewed"
        )

        for block, rows, release_status in (
            (qced_block, qced, "public"),
            (notqced_block, notqced, "private"),
        ):
            block.start_datetime = rows.DateMeasured.min()
            block.end_datetime = rows.DateMeasured.max()

            if not deployments:
                logger.critical(
                    f"Thing with PointID={pointid} has no deployments. Skipping water levels {release_status} block"
                )
                errors.append({"pointid": pointid, "error": "no deployments"})
                continue

            if rows.empty:
                logger.info(f"no {release_status} records for pointid {pointid}")
                continue

            observations = []

            deps_sorted = sorted(
                deployments, key=lambda d: Timestamp(d.installation_date)
            )

            for row in rows.itertuples():
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
                    continue

                try:
                    payload = dict(
                        parameter_id=groundwater_parameter_id,
                        deployment_id=deployment.id,
                        observation_datetime=row.DateMeasured,
                        value=row.DepthToWaterBGS,
                        release_status=release_status,
                    )
                    obspayload = CreateTransducerObservation.model_validate(
                        payload
                    ).model_dump()
                    observations.append(TransducerObservation(**obspayload))
                except ValidationError as e:
                    logger.critical(f"Observation validation error: {e.errors()}")
                    errors.append({"pointid": pointid, "error": e.errors()})

            session.bulk_save_objects(observations)
            session.add(block)
            logger.info(
                f"Added {len(observations)} water levels {release_status} block"
            )
            try:
                session.commit()
            except Exception as e:
                errors.append({"pointid": pointid, "error": e})
                logger.critical(
                    f"Error committing water levels {release_status} block: {e}"
                )
                session.rollback()
                continue

    # convert nodeployments to errors
    for pointid, (min_date, max_date) in nodeployments.items():
        errors.append(
            {
                "table": source_table,
                "pointid": pointid,
                "error": f"no deployment between {min_date} and {max_date}",
            }
        )

    return input_df, cleaned_df, errors


# ============= EOF =============================================
