# ===============================================================================
# Copyright 2026 ross
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
"""
Proves the Dagster+ runtime can reach Ocotillo Postgres.

Dagster+ Serverless runs outside the VPC, so Cloud SQL's private IP is
unreachable from it -- the connection has to go through the Cloud SQL connector
instead. That is the single riskiest assumption in the foundations task, and it
fails at run time rather than at deploy time. This asset makes it fail loudly,
on its own, in an asset whose only job is to fail there.

It reads and never writes: connectivity and permission are separable problems,
and a write here would leave test rows in a real table.
"""

from dagster import AssetExecutionContext, MetadataValue, Output, asset

from automated_ingestion.defs.resources import OcotilloDatabase


@asset(
    group_name="operations",
    description="Reads from Ocotillo Postgres to prove the runtime can connect.",
)
def database_connectivity(
    context: AssetExecutionContext, database: OcotilloDatabase
) -> Output[int]:
    """Count transducer observations, returning the count as metadata."""
    from sqlalchemy import func, select

    from db.transducer import TransducerObservation

    with database.session() as session:
        count = session.scalar(select(func.count()).select_from(TransducerObservation))

    count = int(count or 0)
    context.log.info("connected to Ocotillo; transducer_observation rows: %s", count)
    return Output(
        count,
        metadata={
            "transducer_observation_rows": MetadataValue.int(count),
            "note": MetadataValue.text(
                "Read-only. A failure here is connectivity or grants, not data."
            ),
        },
    )


# ============= EOF =============================================
