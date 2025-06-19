# ===============================================================================
# Copyright 2025 ross
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
Returns a regex pattern to match query strings.
The pattern matches the following structure:
- A field name (alphanumeric characters, underscores, or hyphens)
- An operator (e.g., 'eq', 'ne', 'gt', 'lt', etc.)
- A value (which can be a boolean, number, or string)
"""
import re


QUERY_REGEX = re.compile(
    r"(?P<field>[a-zA-Z_]+(?:\.[a-zA-Z_]+)?)\s+"
    r"(?P<operator>eq|ne|gt|lt|ge|le|like|between)\s+"
    r"(?P<value>'[^']*'|"
    r"true|"
    r"false|\d+(\.\d+)?|"
    r"\[\s*\d+(\.\d+)?\s*,\s*\d+(\.\d+)?\s*\])"
)
# ============= EOF =============================================
