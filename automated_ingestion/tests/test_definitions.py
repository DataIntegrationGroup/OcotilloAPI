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
The code location loads.

Cheap, but it is the check that catches the failure this package is most prone
to: a Dagster+ deploy that builds fine and then cannot import.
"""

from dagster import AssetKey, Definitions

from automated_ingestion.defs.definitions import defs


def test_definitions_object_is_loadable():
    assert isinstance(defs, Definitions)


def test_heartbeat_asset_is_registered():
    assert AssetKey(["ingestion_heartbeat"]) in defs.resolve_all_asset_keys()


def test_heartbeat_materializes_without_external_dependencies():
    from dagster import materialize

    from automated_ingestion.defs.assets.heartbeat import ingestion_heartbeat

    result = materialize([ingestion_heartbeat])
    assert result.success


# ============= EOF =============================================
