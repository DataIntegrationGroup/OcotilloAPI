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
Unit tests for AMPAPI date field population during AMPAPI → NMSampleLocations migration.

These tests verify that:
1. Location.nma_date_created is populated from CSV DateCreated (read-only post-migration)
2. Location.nma_site_date is populated from CSV SiteDate if not null (read-only post-migration)
"""
import datetime
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import pytest

from transfers.util import make_location


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_lexicon_mapper():
    """Fixture to mock lexicon_mapper for all transfer tests"""
    with patch("transfers.util.lexicon_mapper") as mock:
        mock.map_value.return_value = "GPS"
        yield mock


# ============================================================================
# LOCATION AMPAPI DATE TESTS (Read-Only Post-Migration)
# ============================================================================


def test_make_location_with_both_legacy_dates(mock_lexicon_mapper):
    """Test that make_location populates both nma_date_created and nma_site_date"""

    # Create a mock CSV row with both DateCreated and SiteDate
    row = pd.Series(
        {
            "PointID": "TEST-001",
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2014-04-03 00:00:00.000",
            "SiteDate": "2002-12-10 00:00:00.000",
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 1,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}

    # Call make_location
    location, elevation_method = make_location(row, elevations)

    # Verify nma_date_created is set from DateCreated
    assert location.nma_date_created is not None
    assert location.nma_date_created == datetime.date(2014, 4, 3)

    # Verify nma_site_date is set from SiteDate
    assert location.nma_site_date is not None
    assert location.nma_site_date == datetime.date(2002, 12, 10)

    # Verify created_at is NOT set during migration (it's auto-set by AutoBaseMixin on save)
    assert location.created_at is None


def test_make_location_with_only_date_created(mock_lexicon_mapper):
    """Test that make_location handles locations with only DateCreated (no SiteDate)"""
    row = pd.Series(
        {
            "PointID": "TEST-002",
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2014-04-03 00:00:00.000",
            "SiteDate": None,  # No SiteDate
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 2,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify nma_date_created is set
    assert location.nma_date_created == datetime.date(2014, 4, 3)

    # Verify nma_site_date is null (91% of locations don't have SiteDate)
    assert location.nma_site_date is None


def test_make_location_with_site_date_later_than_date_created(mock_lexicon_mapper):
    """Test data anomaly: SiteDate is later than DateCreated (should still be accepted)"""
    row = pd.Series(
        {
            "PointID": "TEST-003",
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2010-01-15 00:00:00.000",
            "SiteDate": "2015-06-20 00:00:00.000",  # Later than DateCreated (anomaly)
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 3,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Both dates should be preserved as-is, regardless of order
    assert location.nma_date_created == datetime.date(2010, 1, 15)
    assert location.nma_site_date == datetime.date(2015, 6, 20)


def test_make_location_with_very_old_site_date(mock_lexicon_mapper):
    """Test that very old SiteDates (1950s) are preserved correctly"""
    row = pd.Series(
        {
            "PointID": "SM-0227",  # Real example from dataset
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2008-05-28 00:00:00.000",
            "SiteDate": "1954-05-01 00:00:00.000",  # 54 years earlier!
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 4,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify very old date is preserved
    assert location.nma_site_date == datetime.date(1954, 5, 1)
    assert location.nma_date_created == datetime.date(2008, 5, 28)

    # Verify 54-year time gap
    time_gap = (location.nma_date_created - location.nma_site_date).days
    assert time_gap == 19751  # Approximately 54 years


def test_make_location_legacy_dates_are_date_not_datetime(mock_lexicon_mapper):
    """Test that AMPAPI date fields are Date type (not DateTime)"""
    row = pd.Series(
        {
            "PointID": "TEST-004",
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2014-04-03 10:30:45.123",  # Has time component
            "SiteDate": "2002-12-10 14:22:33.456",  # Has time component
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 5,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify they are date objects (not datetime)
    assert isinstance(location.nma_date_created, datetime.date)
    assert not isinstance(location.nma_date_created, datetime.datetime)

    assert isinstance(location.nma_site_date, datetime.date)
    assert not isinstance(location.nma_site_date, datetime.datetime)

    # Verify time component is stripped
    assert location.nma_date_created == datetime.date(2014, 4, 3)
    assert location.nma_site_date == datetime.date(2002, 12, 10)


def test_make_location_legacy_dates_independent_of_created_at(mock_lexicon_mapper):
    """Test that AMPAPI dates don't affect created_at timestamp"""
    row = pd.Series(
        {
            "PointID": "TEST-005",
            "Easting": 350000,
            "Northing": 3880000,
            "DateCreated": "2014-04-03 00:00:00.000",
            "SiteDate": "2002-12-10 00:00:00.000",
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": 6,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        }
    )

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # created_at should be None during transfer (auto-set by AutoBaseMixin on save)
    assert location.created_at is None

    # legacy fields should be Date (no timezone)
    assert isinstance(location.nma_date_created, datetime.date)
    assert isinstance(location.nma_site_date, datetime.date)

    # Legacy fields should be populated
    assert location.nma_date_created is not None
    assert location.nma_site_date is not None


# ============================================================================
# DATA COVERAGE TESTS (Simulating Migration Statistics)
# ============================================================================


def test_location_legacy_date_coverage_statistics(mock_lexicon_mapper):
    """Test that migration preserves expected percentages of AMPAPI dates"""

    def create_test_row(i, has_site_date):
        """Helper to create test row with common fields"""
        return pd.Series({
            "PointID": f"TEST-{i:03d}",
            "Easting": 350000 + i,
            "Northing": 3880000 + i,
            "DateCreated": "2014-04-03 00:00:00.000",
            "SiteDate": "2002-12-10 00:00:00.000" if has_site_date else None,
            "Altitude": 1558.8,
            "AltDatum": "NAVD88",
            "AltitudeMethod": "GPS",
            "LocationId": i,
            "PublicRelease": True,
            "CoordinateNotes": None,
            "LocationNotes": None,
            "AltitudeAccuracy": None,
        })

    # Simulate 100 location records from CSV (9% with SiteDate, 91% without)
    locations_created = 0
    locations_with_site_date = 0
    elevations = {}

    for i in range(100):
        row = create_test_row(i, has_site_date=(i < 9))
        location, _ = make_location(row, elevations)

        # Count coverage
        if location.nma_date_created is not None:
            locations_created += 1
        if location.nma_site_date is not None:
            locations_with_site_date += 1

    # Verify expected coverage
    assert locations_created == 100  # 100% should have nma_date_created
    assert locations_with_site_date == 9  # 9% should have nma_site_date


# ============================================================================
# EOF
# ============================================================================
