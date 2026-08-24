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
Domain rules: business knowledge expressed as plain Python.

Modules in this package must not import ``fastapi``, ``sqlalchemy``, ``pydantic``,
``httpx``, or anything from ``api/``, ``db/``, ``schemas/``, or ``services/``.
That restriction is the point: everything here is callable, and testable, without
a database session, an HTTP request, or a network round trip.

Callers in ``services/`` are responsible for loading data, calling into these
rules, and persisting the result.

See ``ADR4.md`` for the layering rationale.
"""

# ============= EOF =============================================
