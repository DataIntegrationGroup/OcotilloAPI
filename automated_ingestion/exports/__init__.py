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
Bulk exports: files built from Ocotillo's own data and published for download.

Ingestion brings data in; this package sends it out. Each export runs its heavy
steps as Cloud Run job executions, launched and watched by Dagster assets in
``automated_ingestion.defs.assets``.
"""

# ============= EOF =============================================
