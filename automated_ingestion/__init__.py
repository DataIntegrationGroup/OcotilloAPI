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
Automated ingestion: scheduled pipelines that land external monitoring data in
Ocotillo without anyone hand-carrying a file.

This package is deployed as its own Dagster+ code location, separate from the
API process, but it lives in this repository so the loader can import ``db/``
models and ``domain/`` rules directly instead of maintaining a second copy of
the Ocotillo schema elsewhere.

Shape of a source: a dlt pipeline extracts the vendor API into a GCS raw zone,
an adapter maps raw records onto Ocotillo structures, and a loader writes them
to Postgres over a direct connection. San Acacia Reach (Van Essen divers) is
the first source; ``shared/`` holds what later sources reuse.

See ``docs/automated-ingestion-pipeline-plan.md``.

Importing this package puts the repository root on ``sys.path``. That is
unusual and deliberate. The Dagster+ image copies the repository to
``/opt/dagster/app`` but never installs it -- the generated requirements omit
the project, and the build template only runs ``pip install .`` when a
``setup.py`` exists -- so ``db`` and ``domain`` are importable only while that
directory happens to be on the path. It is, when Dagster loads the code
location; it is not guaranteed in the separate process that executes a step,
which is where the loader's imports actually run. Locally the editable install
hides the difference entirely, so the failure appears only once deployed.
"""

import sys as _sys
from pathlib import Path as _Path

_REPOSITORY_ROOT = _Path(__file__).resolve().parent.parent
if str(_REPOSITORY_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPOSITORY_ROOT))

# ============= EOF =============================================
