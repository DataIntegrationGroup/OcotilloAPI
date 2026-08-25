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
San Acacia Reach -- 33 Van Essen divers, one depth-to-groundwater series each.

The pilot source: small and already mapped, so it exercises the whole path end
to end without a large or unfamiliar dataset complicating the first build.

Readings come from the private Diver-HUB API, which shapes the extraction in
two ways. Requests carry a JWT good for one hour, so anything long-running
refreshes mid-run rather than authenticating once at the start. And
``DiverData/ByMonitoringPoint/{id}`` returns HTTP 500 when asked for too wide a
span instead of paginating, so reads are always bounded windows in Unix
seconds -- roughly three months is known to work.

Readings land on the **ground-surface** datum (Van Essen's ``gs``
arrays, never ``vrd``), public but provisional, and always ``not reviewed`` --
the vendor's own approval flag records what the vendor approved, not a Bureau
review.
"""

# ============= EOF =============================================
