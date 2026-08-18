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
dlt resources for the Van Essen API.

Two resources: ``locations`` (33 wells, ``replace``, one call) and ``readings``
(per-point, ``append``, incremental on the reading timestamp). Built under BDMS
tasks 2.2 and 2.3; 2.3 waits on the vendor-side endpoint failure.
"""

# ============= EOF =============================================
