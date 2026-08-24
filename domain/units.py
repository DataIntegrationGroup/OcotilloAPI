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
Unit conversion.

This is the single definition of the foot/meter relationship for application
code. ``services/util.py`` re-exports these names, so existing imports continue
to work; new code should import from here.

Alembic revisions deliberately keep their own copy of the constant. A migration
must reproduce the arithmetic it ran with at the time it was written, so it
cannot track a moving import.
"""

METERS_TO_FEET = 3.28084


def convert_ft_to_m(feet: float | None, ndigits: int = 6) -> float | None:
    """Convert a length from feet to meters."""
    if feet is None:
        return None
    return round(feet / METERS_TO_FEET, ndigits)


def convert_m_to_ft(meters: float | None, ndigits: int = 6) -> float | None:
    """Convert a length from meters to feet."""
    if meters is None:
        return None
    return round(meters * METERS_TO_FEET, ndigits)


CENTIMETERS_PER_METER = 100.0


def convert_cm_to_ft(centimeters: float | None, ndigits: int = 6) -> float | None:
    """Convert a length from centimeters to feet.

    Diver-HUB reports water levels in centimeters while Ocotillo stores feet,
    so every ingested reading passes through here.
    """
    if centimeters is None:
        return None
    return round(centimeters / CENTIMETERS_PER_METER * METERS_TO_FEET, ndigits)


# ============= EOF =============================================
