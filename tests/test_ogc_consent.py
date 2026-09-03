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
"""The consent gate on the public collections, and its second copy.

`c5d6e7f8a9b0` wraps each published column in the consent its data type
requires, and it has to restate which type each column belongs to, because a
view cannot read `core/data-type-fields.yml`. Its docstring claims this file
asserts the two agree. It did not exist; two copies of a security baseline
with nothing comparing them is exactly how they drift.
"""

import pytest

from alembic.versions.c5d6e7f8a9b0_gate_public_ogc_columns_on_consent import (
    WATER_WELLS_COLUMNS,
)
from services.field_projection import LOCATION, THING, _data_type_configuration

# Columns the classification cannot speak for, and why. Anything else in the
# view must match the YAML.
UNCLASSIFIED = {
    # Derived from observations rather than stored on either entity, so no
    # column classifies it. It is a fact about the readings.
    "last_observation_date": "water level",
    # `point` is the PostGIS geometry that `latitude`/`longitude` stand in for
    # in the classification, so it is checked against those instead.
    "point": "site metadata",
}


def _classification(entity):
    always, by_data_type = _data_type_configuration()[entity]
    mapping = {field: None for field in always}
    for data_type, fields in by_data_type.items():
        for field in fields:
            mapping[field] = data_type
    return mapping


@pytest.fixture(scope="module")
def classified():
    """Column -> data type, across both entities the wells view draws from."""
    merged = _classification(THING)
    merged.update(_classification(LOCATION))
    return merged


class TestTheViewAgreesWithTheClassification:
    def test_every_column_is_accounted_for(self, classified):
        """No column in the view is unclassified and unexplained."""
        for column, _, _ in WATER_WELLS_COLUMNS:
            assert column in classified or column in UNCLASSIFIED, (
                f"{column} is published by ogc_water_wells and belongs to no "
                "data type. Classify it, or list it in UNCLASSIFIED with a "
                "reason."
            )

    def test_the_data_types_match(self, classified):
        """The migration's restated type equals the YAML's, column by column."""
        mismatched = []
        for column, data_type, _ in WATER_WELLS_COLUMNS:
            if column in UNCLASSIFIED:
                continue
            expected = classified.get(column)
            if expected != data_type:
                mismatched.append((column, data_type, expected))

        assert (
            not mismatched
        ), "c5d6e7f8a9b0 and core/data-type-fields.yml disagree: " + ", ".join(
            f"{column} is '{migration}' in the view and '{yaml}' in the "
            f"classification"
            for column, migration, yaml in mismatched
        )

    def test_geometry_follows_the_coordinates_it_stands_in_for(self, classified):
        """Nulling `point` has to mean the same as nulling lat/lon."""
        assert classified["latitude"] == UNCLASSIFIED["point"]
        assert classified["longitude"] == UNCLASSIFIED["point"]

    def test_ungated_columns_are_the_ungrantable_ones(self, classified):
        """A column the view publishes unconditionally is in `always`.

        `always` is not grantable and so is not consentable: the key and the
        release state are what make the row interpretable at all.
        """
        for column, data_type, _ in WATER_WELLS_COLUMNS:
            if data_type is None and column not in UNCLASSIFIED:
                assert classified[column] is None, (
                    f"{column} is published without a consent check but "
                    f"belongs to '{classified[column]}', which someone can "
                    "revoke."
                )
