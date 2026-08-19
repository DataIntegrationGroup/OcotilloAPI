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

The image installs this repository as a package (see
``dagster_cloud_post_install.sh``), so ``db``, ``domain``, and the rest resolve
from site-packages rather than from whatever happens to be on ``sys.path``. That
matters because the process that loads the code location and the process that
executes a step do not agree about the path, and the loader's imports run in the
second one. Locally an editable install produces the same result, which is why
the difference is invisible until deployment.
"""

# ============= EOF =============================================
