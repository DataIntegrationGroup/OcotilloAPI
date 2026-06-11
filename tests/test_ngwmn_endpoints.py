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
Tests for the /ngwmn endpoints backed by the view_NGWMN_* views, which are
sourced from the new Ocotillo data model (thing/well_screen/observation/
thing_geologic_formation_association) rather than the legacy NMA_view_NGWMN_*
copy tables.
"""

from xml.etree import ElementTree as etree

import pytest
from sqlalchemy import delete

from db import (
    FieldActivity,
    FieldEvent,
    GeologicFormation,
    Observation,
    Sample,
    Thing,
    ThingGeologicFormationAssociation,
    WellCasingMaterial,
    WellScreen,
)
from db.engine import session_ctx
from tests import client, get_parameter_id

POINT_ID = "NGWMN-TEST-0001"


@pytest.fixture(scope="module")
def ngwmn_well():
    """A public water well with casing, screen, lithology, and water levels."""
    with session_ctx() as session:
        thing = Thing(
            name=POINT_ID,
            thing_type="water well",
            release_status="public",
            well_depth=150.0,
            well_casing_depth=120.5,
        )
        session.add(thing)
        session.flush()

        session.add(
            WellScreen(
                thing_id=thing.id,
                screen_depth_top=80.0,
                screen_depth_bottom=120.0,
                screen_description="4in slotted",
                release_status="public",
            )
        )
        session.add(
            WellCasingMaterial(
                thing_id=thing.id, material="Steel", release_status="public"
            )
        )

        formation = GeologicFormation(
            formation_code=None,
            lithology="Sandstone",
            release_status="public",
        )
        session.add(formation)
        session.flush()
        session.add(
            ThingGeologicFormationAssociation(
                thing_id=thing.id,
                geologic_formation_id=formation.id,
                top_depth=0.0,
                bottom_depth=60.0,
                release_status="public",
            )
        )

        event = FieldEvent(
            thing_id=thing.id,
            event_date="2024-03-15T19:00:00Z",
            release_status="public",
        )
        session.add(event)
        session.flush()
        activity = FieldActivity(
            field_event_id=event.id,
            activity_type="groundwater level",
            release_status="public",
        )
        session.add(activity)
        session.flush()

        parameter_id = get_parameter_id("groundwater level", "Field Parameter")

        observations = [
            # Real time component: 19:00 UTC is 13:00 MDT, so the measured
            # date is 2024-03-15 local. BGS = 50.0 - 2.5 = 47.50.
            {
                "sample_name": f"{POINT_ID}-wl-1",
                "sample_method": "Steel-tape measurement",
                "observation_datetime": "2024-03-15T19:00:00Z",
                "value": 50.0,
                "measuring_point_height": 2.5,
                "nma_data_quality": "Water level accurate to within two hundreths of a foot",
                "release_status": "public",
            },
            # Midnight UTC means no time was measured during transfer, so the
            # UTC date is kept. No MP height: BGS = value.
            {
                "sample_name": f"{POINT_ID}-wl-2",
                "sample_method": "Pressure-gage measurement",
                "observation_datetime": "2024-04-01T00:00:00Z",
                "value": 33.0,
                "measuring_point_height": None,
                "nma_data_quality": "Water level accurate to within one foot",
                "release_status": "public",
            },
            # Private observations must not appear in the NGWMN export.
            {
                "sample_name": f"{POINT_ID}-wl-3",
                "sample_method": "Steel-tape measurement",
                "observation_datetime": "2024-05-01T00:00:00Z",
                "value": 12.0,
                "measuring_point_height": None,
                "nma_data_quality": None,
                "release_status": "private",
            },
        ]
        for obs in observations:
            sample = Sample(
                field_activity_id=activity.id,
                sample_date=obs["observation_datetime"],
                sample_name=obs["sample_name"],
                sample_matrix="water",
                sample_method=obs["sample_method"],
                qc_type="Normal",
                release_status=obs["release_status"],
            )
            session.add(sample)
            session.flush()
            session.add(
                Observation(
                    sample_id=sample.id,
                    parameter_id=parameter_id,
                    observation_datetime=obs["observation_datetime"],
                    value=obs["value"],
                    unit="ft",
                    measuring_point_height=obs["measuring_point_height"],
                    nma_data_quality=obs["nma_data_quality"],
                    release_status=obs["release_status"],
                )
            )
        session.commit()
        thing_id = thing.id
        formation_id = formation.id

    yield POINT_ID

    with session_ctx() as session:
        # Thing delete cascades to screens, casing materials, field events
        # (and through to samples/observations), and formation associations.
        session.execute(delete(Thing).where(Thing.id == thing_id))
        session.execute(
            delete(GeologicFormation).where(GeologicFormation.id == formation_id)
        )
        session.commit()


def test_ngwmn_waterlevels(ngwmn_well):
    response = client.get(f"/ngwmn/waterlevels/{ngwmn_well}")
    assert response.status_code == 200

    root = etree.fromstring(response.content)
    assert root.tag == "WaterLevels"
    levels = root.findall("WaterLevel")
    assert len(levels) == 2

    first, second = levels
    assert first.findtext("PointID") == ngwmn_well
    assert first.findtext("DepthFromLandSurfaceData") == "47.50"
    assert first.findtext("WaterLevelUnits") == "ft bgs"
    assert first.findtext("MeasuringMethod") == "Steel tape"
    assert first.findtext("MeasurementYear") == "2024"
    assert first.findtext("MeasurementMonth") == "3"
    assert first.findtext("MeasurementDay") == "15"
    assert first.findtext("WaterLevelAccuracy") == "0.02 ft"

    assert second.findtext("DepthFromLandSurfaceData") == "33.00"
    assert second.findtext("MeasuringMethod") == "Pressure gauge"
    assert second.findtext("MeasurementMonth") == "4"
    assert second.findtext("MeasurementDay") == "1"
    assert second.findtext("WaterLevelAccuracy") == "1.0 ft"


def test_ngwmn_wellconstruction(ngwmn_well):
    response = client.get(f"/ngwmn/wellconstruction/{ngwmn_well}")
    assert response.status_code == 200

    root = etree.fromstring(response.content)
    assert root.tag == "Casings"
    casings = root.findall("Casing")
    assert len(casings) == 1

    casing = casings[0]
    assert casing.findtext("PointID") == ngwmn_well
    assert float(casing.findtext("CasingTop")) == 0.0
    assert float(casing.findtext("CasingBottom")) == 120.5
    assert casing.findtext("CasingDepthUnits") == "ft bgs"
    assert float(casing.findtext("ScreenTop")) == 80.0
    assert float(casing.findtext("ScreenBottom")) == 120.0
    assert casing.findtext("ScreenDescription") == "4in slotted"


def test_ngwmn_lithology(ngwmn_well):
    response = client.get(f"/ngwmn/lithology/{ngwmn_well}")
    assert response.status_code == 200

    root = etree.fromstring(response.content)
    assert root.tag == "Lithologies"
    lithologies = root.findall("Lithology")
    assert len(lithologies) == 1

    lithology = lithologies[0]
    assert lithology.findtext("PointID") == ngwmn_well
    assert float(lithology.findtext("TopDepth")) == 0.0
    assert float(lithology.findtext("BottomDepth")) == 60.0
    assert lithology.findtext("Units") == "feet"
    assert lithology.findtext("Description") == "Sandstone"


def test_ngwmn_unknown_pointid_returns_empty():
    response = client.get("/ngwmn/waterlevels/NO-SUCH-POINTID")
    assert response.status_code == 200
    root = etree.fromstring(response.content)
    assert root.tag == "WaterLevels"
    assert len(root.findall("WaterLevel")) == 0


# ============= EOF =============================================
