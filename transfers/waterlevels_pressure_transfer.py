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
from db import Parameter, Thing, Deployment
from db.transducer import TransducerObservation, TransducerObservationBlock
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

    for index, group in gwd:
        pointid = index[0]
        logger.info(f"Processing PointID: {pointid}")

        deployments = (
            session.query(Deployment).join(Thing).where(Thing.name == pointid).all()
        )

        if deployments is None:
            logger.critical(
                f"Thing with PointID={pointid} has no deployment. Skipping water levels"
            )
            continue

        # remove rows with no date measured
        group = group[group.DateMeasured.notna()]

        # sort rows by date measured
        group = group.sort_values(by="DateMeasured")

        qced = group[group.QCed]
        notqced = group[~group.QCed]

        qced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, qc_status="provisional"
        )
        notqced_block = TransducerObservationBlock(
            parameter_id=groundwater_parameter_id, qc_status="unverified"
        )

        for block, rows, release_status in (
            (qced_block, qced, "public"),
            (notqced_block, notqced, "private"),
        ):
            if not rows.empty:
                min_date = rows.DateMeasured.min()
                max_date = rows.DateMeasured.max()
                block.start_datetime = min_date
                block.end_datetime = max_date
                # session.add(block)
                # session.flush()
            else:
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

                observations.append(
                    {
                        "parameter_id": groundwater_parameter_id,
                        "deployment_id": deployment.id,
                        "observation_datetime": row.DateMeasured,
                        "value": row.DepthToWaterBGS,
                        "release_status": release_status,
                    }
                )

            # session.bulk_insert_mappings(TransducerObservation, observations)

            block.observations = [
                TransducerObservation(**payload) for payload in observations
            ]
            session.add(block)
            session.commit()


# ============= EOF =============================================
