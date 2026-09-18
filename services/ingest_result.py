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
"""What an ingest hands back to whoever ran it.

Every importer behind an `oco` ingest command -- well inventory, water levels,
the LIMS chemistry workbook, the chemistry field sheet -- returned its own
four-field dataclass with the same fields and the same meaning. One type means
the shared CLI rendering in :mod:`cli.ingest_report` has one shape to read, and
a new importer has nothing to declare.

``payload`` is deliberately a plain dict rather than a schema: each importer
reports different things (created samples, matched samples, imported wells), and
the renderers reach for the keys they know about. What every payload does carry
is a ``summary`` mapping with ``total_rows_processed``,
``total_rows_imported`` and ``validation_errors_or_warnings``, plus a
``validation_errors`` list -- that much the shared summary block depends on.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngestResult:
    """The outcome of one ingest run.

    ``exit_code`` is what the CLI exits with: zero when the run is something an
    operator can accept, non-zero when it is not. ``stdout`` carries a
    machine-readable rendering when a command offers one (``--output json``),
    and ``stderr`` the human-readable failure text.
    """

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


# ============= EOF =============================================
