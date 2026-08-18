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


def test_loading_definitions_does_not_import_db_engine():
    # db.engine builds its engine at import time, so listing assets must not
    # reach it. Checking sys.modules in-process would only observe whichever
    # test imported it first, so ask a clean interpreter instead.
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import automated_ingestion.defs.definitions as d; "
            "import sys; "
            "assert d.defs is not None; "
            "print('db.engine' in sys.modules)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", result.stdout


def test_importing_the_package_makes_the_repository_importable():
    # The deployed image never installs this project, so `db` and `domain`
    # resolve only if the repository root is on sys.path. Locally an editable
    # install provides that and hides the difference, which is why this failed
    # only once deployed -- the code location loaded fine and the step that
    # imported db died.
    import sys

    import automated_ingestion

    assert str(automated_ingestion._REPOSITORY_ROOT) in sys.path


def test_db_imports_from_an_unrelated_working_directory():
    # Reproduces the deployed condition: a process whose cwd is not the
    # repository. The lazy imports in the resource and the connectivity asset
    # run at step execution, not at load, so this is the path that broke.
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import automated_ingestion; "
            "from db.transducer import TransducerObservation; "
            "print(TransducerObservation.__tablename__)",
        ],
        capture_output=True,
        text=True,
        cwd="/",
    )
    assert result.returncode == 0, result.stderr
    assert "transducer_observation" in result.stdout


# ============= EOF =============================================
