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
A trivial asset that proves the code location deploys and materializes.

It touches nothing -- no database, no network, no GCS -- so a failure here is
unambiguously a packaging or deployment problem rather than a credential or
connectivity one. The Postgres connectivity check that BDMS task 1.4 calls for
is a separate asset, added when the least-privilege role exists.
"""

from datetime import datetime, timezone

from dagster import AssetExecutionContext, asset


@asset(
    group_name="operations",
    description="Static heartbeat proving the code location loaded and can run.",
)
def ingestion_heartbeat(context: AssetExecutionContext) -> str:
    """Return the materialization timestamp."""
    stamp = datetime.now(timezone.utc).isoformat()
    context.log.info("automated_ingestion code location alive at %s", stamp)
    return stamp


# ============= EOF =============================================
