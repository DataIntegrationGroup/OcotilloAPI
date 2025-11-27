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
Unit tests for legacy date field population during AMPAPI → NMSampleLocations migration.

These tests verify that:
1. Location.legacy_date_created is populated from CSV DateCreated
2. Location.legacy_site_date is populated from CSV SiteDate (if not null)
3. Thing.well_completed_on is populated from CSV CompletionDate (if not null)
"""
import datetime
from unittest.mock import Mock, patch
import pandas as pd
import pytest

from transfers.util import make_location
from schemas.thing import CreateWell


# ============================================================================
# LOCATION LEGACY DATE TESTS
# ============================================================================


def test_make_location_with_both_legacy_dates():
    """Test that make_location populates both legacy_date_created and legacy_site_date"""
    # Create a mock CSV row with both DateCreated and SiteDate
    row = pd.Series({
        'PointID': 'TEST-001',
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2014-04-03 00:00:00.000',
        'SiteDate': '2002-12-10 00:00:00.000',
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 1,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}

    # Call make_location
    location, elevation_method = make_location(row, elevations)

    # Verify legacy_date_created is set from DateCreated
    assert location.legacy_date_created is not None
    assert location.legacy_date_created == datetime.date(2014, 4, 3)

    # Verify legacy_site_date is set from SiteDate
    assert location.legacy_site_date is not None
    assert location.legacy_site_date == datetime.date(2002, 12, 10)

    # Verify created_at is still set (should be the later date)
    assert location.created_at is not None


def test_make_location_with_only_date_created():
    """Test that make_location handles locations with only DateCreated (no SiteDate)"""
    row = pd.Series({
        'PointID': 'TEST-002',
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2014-04-03 00:00:00.000',
        'SiteDate': None,  # No SiteDate
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 2,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify legacy_date_created is set
    assert location.legacy_date_created == datetime.date(2014, 4, 3)

    # Verify legacy_site_date is null (91% of locations don't have SiteDate)
    assert location.legacy_site_date is None


def test_make_location_with_site_date_later_than_date_created():
    """Test data anomaly: SiteDate is later than DateCreated (should still be accepted)"""
    row = pd.Series({
        'PointID': 'TEST-003',
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2010-01-15 00:00:00.000',
        'SiteDate': '2015-06-20 00:00:00.000',  # Later than DateCreated (anomaly)
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 3,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Both dates should be preserved as-is, regardless of order
    assert location.legacy_date_created == datetime.date(2010, 1, 15)
    assert location.legacy_site_date == datetime.date(2015, 6, 20)


def test_make_location_with_very_old_site_date():
    """Test that very old SiteDates (1950s) are preserved correctly"""
    row = pd.Series({
        'PointID': 'SM-0227',  # Real example from dataset
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2008-05-28 00:00:00.000',
        'SiteDate': '1954-05-01 00:00:00.000',  # 54 years earlier!
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 4,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify very old date is preserved
    assert location.legacy_site_date == datetime.date(1954, 5, 1)
    assert location.legacy_date_created == datetime.date(2008, 5, 28)

    # Verify 54-year time gap
    time_gap = (location.legacy_date_created - location.legacy_site_date).days
    assert time_gap == 19751  # Approximately 54 years


def test_make_location_legacy_dates_are_date_not_datetime():
    """Test that legacy date fields are Date type (not DateTime)"""
    row = pd.Series({
        'PointID': 'TEST-004',
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2014-04-03 10:30:45.123',  # Has time component
        'SiteDate': '2002-12-10 14:22:33.456',  # Has time component
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 5,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # Verify they are date objects (not datetime)
    assert isinstance(location.legacy_date_created, datetime.date)
    assert not isinstance(location.legacy_date_created, datetime.datetime)

    assert isinstance(location.legacy_site_date, datetime.date)
    assert not isinstance(location.legacy_site_date, datetime.datetime)

    # Verify time component is stripped
    assert location.legacy_date_created == datetime.date(2014, 4, 3)
    assert location.legacy_site_date == datetime.date(2002, 12, 10)


def test_make_location_legacy_dates_independent_of_created_at():
    """Test that legacy dates don't affect created_at timestamp"""
    row = pd.Series({
        'PointID': 'TEST-005',
        'Easting': 350000,
        'Northing': 3880000,
        'DateCreated': '2014-04-03 00:00:00.000',
        'SiteDate': '2002-12-10 00:00:00.000',
        'Altitude': 1558.8,
        'AltDatum': 'NAVD88',
        'AltitudeMethod': 'GPS',
        'LocationId': 6,
        'PublicRelease': True,
        'CoordinateNotes': None,
        'LocationNotes': None,
        'AltitudeAccuracy': None,
    })

    elevations = {}
    location, elevation_method = make_location(row, elevations)

    # created_at should be a DateTime (with timezone)
    assert isinstance(location.created_at, datetime.datetime)

    # legacy fields should be Date (no timezone)
    assert isinstance(location.legacy_date_created, datetime.date)
    assert isinstance(location.legacy_site_date, datetime.date)

    # They should be independent
    assert location.created_at is not None
    assert location.legacy_date_created is not None
    assert location.legacy_site_date is not None


# ============================================================================
# WELL COMPLETION DATE TESTS
# ============================================================================


def test_create_well_schema_accepts_well_completed_on():
    """Test that CreateWell schema accepts well_completed_on from CSV CompletionDate"""
    # Simulate data from CSV transfer
    well_data = {
        'location_id': 1,
        'name': 'TEST-WELL-001',
        'well_completed_on': datetime.date(2004, 8, 8),  # From CSV CompletionDate
        'hole_depth': 100.0,
        'well_depth': 95.0,
        'measuring_point_height': 2.5,
        'measuring_point_description': 'top of casing',
        'release_status': 'public',
    }

    # Validate using CreateWell schema
    schema = CreateWell(**well_data)

    assert schema.well_completed_on == datetime.date(2004, 8, 8)


def test_create_well_schema_well_completed_on_optional():
    """Test that well_completed_on is optional (70% of wells don't have CompletionDate)"""
    well_data = {
        'location_id': 1,
        'name': 'TEST-WELL-002',
        'hole_depth': 100.0,
        'well_depth': 95.0,
        'measuring_point_height': 2.5,
        'measuring_point_description': 'top of casing',
        'release_status': 'public',
        # No well_completed_on provided
    }

    # Should not raise validation error
    schema = CreateWell(**well_data)

    # Field should be optional
    assert hasattr(schema, 'well_completed_on')
    # Value should be None when not provided
    assert schema.well_completed_on is None


def test_create_well_with_very_old_completion_date():
    """Test that very old completion dates (1936) are accepted"""
    well_data = {
        'location_id': 1,
        'name': 'HISTORICAL-WELL',
        'well_completed_on': datetime.date(1936, 1, 1),  # Oldest well in dataset
        'hole_depth': 100.0,
        'well_depth': 95.0,
        'measuring_point_height': 2.5,
        'measuring_point_description': 'top of casing',
        'release_status': 'public',
    }

    schema = CreateWell(**well_data)

    assert schema.well_completed_on == datetime.date(1936, 1, 1)


def test_create_well_completed_on_is_date_not_datetime():
    """Test that well_completed_on is Date type (not DateTime)"""
    well_data = {
        'location_id': 1,
        'name': 'TEST-WELL-003',
        'well_completed_on': datetime.date(2004, 8, 8),  # Date, not DateTime
        'hole_depth': 100.0,
        'well_depth': 95.0,
        'measuring_point_height': 2.5,
        'measuring_point_description': 'top of casing',
        'release_status': 'public',
    }

    schema = CreateWell(**well_data)

    # Should accept date type
    assert isinstance(schema.well_completed_on, datetime.date)
    assert not isinstance(schema.well_completed_on, datetime.datetime)


# ============================================================================
# DATA COVERAGE TESTS (Simulating Migration Statistics)
# ============================================================================


def test_location_legacy_date_coverage_statistics():
    """Test that migration preserves expected percentages of legacy dates"""
    # Simulate 100 location records from CSV
    locations_created = 0
    locations_with_site_date = 0

    for i in range(100):
        if i < 9:  # 9% have SiteDate
            row = pd.Series({
                'PointID': f'TEST-{i:03d}',
                'Easting': 350000 + i,
                'Northing': 3880000 + i,
                'DateCreated': '2014-04-03 00:00:00.000',
                'SiteDate': '2002-12-10 00:00:00.000',
                'Altitude': 1558.8,
                'AltDatum': 'NAVD88',
                'AltitudeMethod': 'GPS',
                'LocationId': i,
                'PublicRelease': True,
                'CoordinateNotes': None,
                'LocationNotes': None,
                'AltitudeAccuracy': None,
            })
        else:  # 91% don't have SiteDate
            row = pd.Series({
                'PointID': f'TEST-{i:03d}',
                'Easting': 350000 + i,
                'Northing': 3880000 + i,
                'DateCreated': '2014-04-03 00:00:00.000',
                'SiteDate': None,
                'Altitude': 1558.8,
                'AltDatum': 'NAVD88',
                'AltitudeMethod': 'GPS',
                'LocationId': i,
                'PublicRelease': True,
                'CoordinateNotes': None,
                'LocationNotes': None,
                'AltitudeAccuracy': None,
            })

        elevations = {}
        location, _ = make_location(row, elevations)

        # Count coverage
        if location.legacy_date_created is not None:
            locations_created += 1

        if location.legacy_site_date is not None:
            locations_with_site_date += 1

    # Verify expected coverage
    assert locations_created == 100  # 100% should have legacy_date_created
    assert locations_with_site_date == 9  # 9% should have legacy_site_date


def test_well_completion_date_coverage_statistics():
    """Test that expected percentage of wells have completion dates"""
    # Simulate 100 wells from CSV
    wells_with_completion_date = 0

    for i in range(100):
        if i < 30:  # 30% have CompletionDate
            well_data = {
                'location_id': 1,
                'name': f'WELL-{i:03d}',
                'well_completed_on': datetime.date(2004, 8, 8),
                'hole_depth': 100.0,
                'well_depth': 95.0,
                'measuring_point_height': 2.5,
                'measuring_point_description': 'top of casing',
                'release_status': 'public',
            }
        else:  # 70% don't have CompletionDate
            well_data = {
                'location_id': 1,
                'name': f'WELL-{i:03d}',
                'hole_depth': 100.0,
                'well_depth': 95.0,
                'measuring_point_height': 2.5,
                'measuring_point_description': 'top of casing',
                'release_status': 'public',
                # No well_completed_on
            }

        schema = CreateWell(**well_data)

        if schema.well_completed_on is not None:
            wells_with_completion_date += 1

    # Verify expected coverage
    assert wells_with_completion_date == 30  # 30% should have completion dates


# ============================================================================
# EOF
# ============================================================================
