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

from enum import Enum


def normalize_for_db(value):
    """
    Recursively convert Python/Pydantic payloads into DB-friendly primitives.

    Dates and datetimes are intentionally preserved as-is. Enum values are
    unwrapped to their underlying primitive values so psycopg2 never sees raw
    Enum objects.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: normalize_for_db(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_for_db(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_for_db(item) for item in value)
    return value


# ============= EOF =============================================
