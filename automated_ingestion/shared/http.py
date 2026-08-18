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
HTTP session construction for vendor APIs.

Centralized so every source inherits the same timeout, retry, and backoff
posture, and so one source's flaky endpoint cannot hang a run indefinitely.
Filled in alongside the first live extraction under BDMS task 2.
"""

# ============= EOF =============================================
