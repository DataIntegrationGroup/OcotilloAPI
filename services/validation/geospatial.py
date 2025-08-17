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
from shapely import wkt


def validate_wkt_geometry(value: str | None) -> str | None:
    """
    Validate that the provided string is a valid WKT geometry.
    Raises ValueError if the geometry is invalid.
    """
    if value is None:
        return value

    try:
        geometry = wkt.loads(value)
        if not geometry.is_valid:
            raise ValueError("WKT geometry is not topologically valid")
        return value
    except Exception as e:
        raise ValueError(f"Invalid WKT geometry: {e}")
# ============= EOF =============================================
