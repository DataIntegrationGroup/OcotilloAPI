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
Unit tests for NGWMN legacy view models.

These tests verify the migration of columns from NGWMN view tables.
"""

from datetime import date
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import (
    NMA_view_NGWMN_WellConstruction,
    NMA_view_NGWMN_WaterLevels,
    NMA_view_NGWMN_Lithology,
)


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


# ===================== WellConstruction tests ==========================
def test_create_ngwmn_well_construction():
    """Test creating an NGWMN well construction record."""
    with session_ctx() as session:
        record = NMA_view_NGWMN_WellConstruction(
            point_id="NG-1001",
            casing_top=10.0,
            casing_bottom=100.0,
            casing_depth_units="ft",
            screen_top=20.0,
            screen_bottom=90.0,
            screen_bottom_unit="ft",
            screen_description="Screen desc",
            casing_description="Casing desc",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.point_id == "NG-1001"

        session.delete(record)
        session.commit()


def test_ngwmn_well_construction_columns():
    """Test that the NGWMN well construction model has expected columns."""
    expected_columns = [
        "id",
        "point_id",
        "casing_top",
        "casing_bottom",
        "casing_depth_units",
        "screen_top",
        "screen_bottom",
        "screen_bottom_unit",
        "screen_description",
        "casing_description",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_view_NGWMN_WellConstruction, column
        ), f"Expected column '{column}' not found in NMA_view_NGWMN_WellConstruction model"


def test_ngwmn_well_construction_table_name():
    """Test that the table name follows convention."""
    assert (
        NMA_view_NGWMN_WellConstruction.__tablename__
        == "NMA_view_NGWMN_WellConstruction"
    )


# ===================== WaterLevels tests ==========================
def test_create_ngwmn_water_levels():
    """Test creating an NGWMN water levels record."""
    with session_ctx() as session:
        record = NMA_view_NGWMN_WaterLevels(
            point_id="NG-2001",
            date_measured=date(2024, 1, 1),
            depth_to_water_bgs=12.3,
            wl_units="ft",
            measurement_method="Tape",
            wl_accuracy=0.1,
            public_release=True,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_view_NGWMN_WaterLevels, ("NG-2001", date(2024, 1, 1)))
        assert fetched is not None
        assert fetched.point_id == "NG-2001"

        session.delete(record)
        session.commit()


def test_ngwmn_water_levels_columns():
    """Test that the NGWMN water levels model has expected columns."""
    expected_columns = [
        "point_id",
        "date_measured",
        "depth_to_water_bgs",
        "wl_units",
        "measurement_method",
        "wl_accuracy",
        "public_release",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_view_NGWMN_WaterLevels, column
        ), f"Expected column '{column}' not found in NMA_view_NGWMN_WaterLevels model"


def test_ngwmn_water_levels_table_name():
    """Test that the table name follows convention."""
    assert NMA_view_NGWMN_WaterLevels.__tablename__ == "NMA_view_NGWMN_WaterLevels"


# ===================== Lithology tests ==========================
def test_create_ngwmn_lithology():
    """Test creating an NGWMN lithology record."""
    with session_ctx() as session:
        record = NMA_view_NGWMN_Lithology(
            object_id=_next_object_id(),
            point_id="NG-3001",
            lithology="Sand",
            term="Term",
            strat_source="Source",
            strat_top=1.0,
            strat_top_unit="ft",
            strat_bottom=5.0,
            strat_bottom_unit="ft",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.object_id is not None
        assert record.point_id == "NG-3001"

        session.delete(record)
        session.commit()


def test_ngwmn_lithology_columns():
    """Test that the NGWMN lithology model has expected columns."""
    expected_columns = [
        "object_id",
        "point_id",
        "lithology",
        "term",
        "strat_source",
        "strat_top",
        "strat_top_unit",
        "strat_bottom",
        "strat_bottom_unit",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_view_NGWMN_Lithology, column
        ), f"Expected column '{column}' not found in NMA_view_NGWMN_Lithology model"


def test_ngwmn_lithology_table_name():
    """Test that the table name follows convention."""
    assert NMA_view_NGWMN_Lithology.__tablename__ == "NMA_view_NGWMN_Lithology"


# ============= EOF =============================================
