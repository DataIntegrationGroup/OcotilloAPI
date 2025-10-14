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
from pydantic import ValidationError

from db import Parameter, Thing, Deployment
from db.transducer import TransducerObservation, TransducerObservationBlock
from schemas.transducer import CreateTransducerObservation
from transfers.logger import logger
from transfers.util import read_csv


def transfer_water_levels_acoustic(session):
    wd = read_csv("WaterLevelsContinuous_Acoustic")
    _transfer_water_levels_continuous(session, wd, "PublicRelease")


def transfer_water_levels_pressure(session):
    wd = read_csv("WaterLevelsContinuous_Pressure")
    _transfer_water_levels_continuous(session, wd, "QCed")


def _transfer_water_levels_continuous(session, wd, partition_field):
    groundwater_parameter_id = (
        session.query(Parameter)
        .filter(Parameter.parameter_name == "groundwater level")
        .one()
        .id
    )

    # group by pointid
    gwd = wd.groupby(["PointID"])

    for index, group in gwd:
        pointid = index[0]
        logger.info(f"Processing PointID: {pointid}")

        deployments = (
            session.query(Deployment).join(Thing).where(Thing.name == pointid).all()
        )

        # remove rows with no date measured
        group = group[group.DateMeasured.notna()]

        # sort rows by date measured
        group = group.sort_values(by="DateMeasured")
        field = getattr(group, partition_field)

        qced = group[field == 1]
        notqced = group[~field == 1]

        qced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, qc_status="verified"
        )
        notqced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, qc_status="unverified"
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
                continue

            if rows.empty:
                continue

            observations = []
            for row in rows.itertuples():
                deployment = next(
                    (
                        d
                        for d in deployments
                        if d.installation_date < row.DateMeasured
                        and (
                            d.removal_date is None or d.removal_date > row.DateMeasured
                        )
                    ),
                    None,
                )

                if deployment is None:
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

            block.observations = observations
            session.add(block)
            session.commit()


# ============= EOF =============================================
