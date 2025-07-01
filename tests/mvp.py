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

def test_add_location_minimum():
    location = {
        "name": "Test Location 1",
        "point": "POINT(10.1 10.1)",
        "visible": True,
    }


def test_add_location_all():
    location = {
        "name": "Test Location 1",
        "point": "POINT(10.1 10.1)",
        "description": 'this is a test location',
        "visible": True,
    }


def test_add_well_minimum():
    well = {
        "location_id": 1,
        "well_type": "Monitoring",
    }


def test_add_well_all():
    well = {
        "location_id": 1,
        "api_id": "1001-0001",
        "ose_pod_id": "RA-0001",
        "well_type": "Monitoring",
        "well_depth": 100.0,
        "hole_depth": 100.0,
        "casing_diameter": 10.0,
        "casing_depth": 20.0,
        "casing_description": 'foo bar',
        "formation_zone": 'San Andres',
        "construction_notes": "this is a test of notes",
    }

def test_add_well_screen_minimum():
    well_screen = {
        "well_id": 1,
        "screen_depth_top": 100.0,
        "screen_depth_bottom": 120.0,
    }


def test_add_well_screen_all():
    well_screen = {
        "well_id": 1,
        "screen_depth_top": 100.0,
        "screen_depth_bottom": 120.0,
        "screen_type": "PVC"
    }


def test_add_owner_with_contacts():
    owner = {
        "name": "The Doe's",
        "contact": [
            {"name": "John Doe", "phone": "123-456-7890", "email": "foo@gmail.com"},
            {
                "name": "Jane Doe",
                "phone": "913-356-7890",
                "email": "jane@gmail.com",
            },
        ],
    }


def test_add_owner_without_contacts():
    owner = {
        "name": "Alice Bob"
    }

def test_add_asset():
    asset = {
        'filename': 'foo.png',
        'storage_service': 'gcs',
        'storage_path': 'gs://...',
        'mime_type': 'image/png',
        'size': 100,
    }


#  ============== optional ? =============
def test_add_lexicon():
    formation = {
        'term': 'San Andres',
        'definition': 'Some sandstone unit',
        'category': 'Formations'
    }

    unit = {"term": "TDS",
            "definition": "Total Dissolved Solids",
            "category": "water_chemistry"}

def test_add_lexicon_triple():
    subject = {
        "term": "MG-030",
        "definition": "magdalena well",
        "category": "location_identifier",
    }
    predicate = "same_as"
    object_ = {
        "term": "USGS1234",
        "definition": "magdalena well",
        "category": "location_identifier",
    }

def test_add_lexicon_triple_existing_subject():
    subject = 'TDS'
    predicate = "same_as"
    object_ = {
        "term": 'Total Dissolved Solids',
        "definition": 'all the solids dissolved in sample',
        "category": "water_chemistry"
    }

def test_add_lexicon_triple_existing():
    subject = 'TDS'
    predicate = "same_as"
    object_ = 'Total Dissolved Solids'


# ============= EOF =============================================
