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
The connectivity asset is wired up, and does not reach the database until run.

Loading the code location must not open a connection: Dagster lists assets far
more often than it runs them, and a code location that needs a database to load
is a code location that breaks whenever the database is briefly unreachable.
"""

from dagster import AssetKey

from automated_ingestion.defs.definitions import defs


def test_connectivity_asset_is_registered():
    assert AssetKey(["database_connectivity"]) in defs.resolve_all_asset_keys()


def test_database_resource_is_provided():
    assert "database" in defs.resources


def test_loading_definitions_opens_no_connection():
    # db.engine builds its engine at import time, so the guard that matters is
    # that importing the definitions module has not imported it.
    import sys

    assert "db.engine" not in sys.modules


# ============= EOF =============================================
