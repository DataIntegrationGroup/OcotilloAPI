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
Reshaping that precedes adaptation.

Less is needed here than the plan first assumed. The retired FROST pipeline
suggested Van Essen returned parallel arrays that had to be zipped into
records; the live API returns ``[{dateAndTime, level}]`` already, and selects
datum and approval through query parameters rather than through which array a
value came from.

What remains for this module is timestamp normalisation and whatever
per-record tidying the live responses turn out to need. Filled in under BDMS
task 3.1, once the probe has run.
"""

# ============= EOF =============================================
