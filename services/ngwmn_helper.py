# ===============================================================================
# Copyright 2018 ross
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
from xml.etree import ElementTree as etree

from db import Thing
from domain.lithology import lithology_code
from db.ngwmn_views import (
    NGWMNLithology,
    NGWMNWaterLevels,
    NGWMNWellConstruction,
    TransducerDailyData,
)


def _as_text(v):
    return "" if v is None else str(v)


# NSMAP = dict(xsi="http://www.w3.org/2001/XMLSchema-instance", xsd="http://www.w3.org/2001/XMLSchema")


def make_lithology_response(point_id, db):
    records = (
        db.query(
            NGWMNLithology.point_id,
            NGWMNLithology.term,
            NGWMNLithology.strat_source,
            NGWMNLithology.strat_top,
            NGWMNLithology.strat_top_unit,
            NGWMNLithology.strat_bottom,
            NGWMNLithology.strat_bottom_unit,
        )
        .filter(NGWMNLithology.point_id == point_id)
        .order_by(NGWMNLithology.strat_top, NGWMNLithology.object_id)
        .all()
    )
    return lithology_xml(records)


def make_well_construction_response(point_id, db):
    records = (
        db.query(
            NGWMNWellConstruction.point_id,
            NGWMNWellConstruction.casing_top,
            NGWMNWellConstruction.casing_bottom,
            NGWMNWellConstruction.casing_depth_units,
            NGWMNWellConstruction.screen_top,
            NGWMNWellConstruction.screen_bottom,
            NGWMNWellConstruction.screen_bottom_unit,
            NGWMNWellConstruction.screen_description,
            NGWMNWellConstruction.casing_description,
        )
        .filter(NGWMNWellConstruction.point_id == point_id)
        .all()
    )
    return well_construction_xml(records)


def make_waterlevels_response(point_id, db):
    manual = (
        db.query(
            NGWMNWaterLevels.point_id,
            NGWMNWaterLevels.date_measured,
            NGWMNWaterLevels.depth_to_water_bgs,
            NGWMNWaterLevels.wl_units,
            NGWMNWaterLevels.measurement_method,
            NGWMNWaterLevels.wl_accuracy,
            NGWMNWaterLevels.public_release,
        )
        .filter(
            NGWMNWaterLevels.point_id == point_id,
            # A null depth is a recorded attempt (dry well, obstruction) with
            # no level to report; NGWMN has nothing to harvest from it.
            NGWMNWaterLevels.depth_to_water_bgs.isnot(None),
        )
        .order_by(NGWMNWaterLevels.date_measured)
        .all()
    )
    # The daily *minimum* depth matches the legacy
    # NMA_WaterLevelsContinuous_Pressure_Daily values (AMP's nightly job
    # published the shallowest reading of each day), keeping the NGWMN
    # record consistent with what was historically harvested.
    pressure = (
        db.query(
            TransducerDailyData.point_id,
            TransducerDailyData.date_measured,
            TransducerDailyData.depth_to_water_bgs_min,
        )
        .join(Thing, Thing.id == TransducerDailyData.thing_id)
        .filter(
            TransducerDailyData.point_id == point_id,
            TransducerDailyData.qced.is_(True),
            TransducerDailyData.parameter_name == "groundwater level",
            TransducerDailyData.depth_to_water_bgs_min.isnot(None),
            Thing.release_status == "public",
        )
        .order_by(TransducerDailyData.date_measured)
        .all()
    )
    return water_levels_xml2(manual, pressure)


# ==================== make xml =======================
def continuous_water_levels_xml(records):
    return make_xml("WaterLevels", records, make_continuous_water_level)


def water_levels_xml(records):
    return make_xml("WaterLevels", records, make_water_level)


def water_levels_xml2(manual, pressure):
    """
    Merge manual measurements (NGWMN_WaterLevels rows) with daily
    transducer aggregates (transducer_daily_data rows). Both row types carry
    (PointID, date, depth to water bgs, ...) in their first three columns.

    When both sources have a measurement on the same date, the manual reading
    wins if it is shallower; either way only one record is emitted per date.
    """
    if not pressure:
        return make_xml("WaterLevels", manual, make_water_level)

    root = etree.Element("WaterLevels")

    manual = list(manual)
    manual_dates = [r[1] for r in manual]
    records = []
    for r in pressure:
        dm = r[1]
        tag = "pressure"
        if dm in manual_dates:
            ri = next(ri for ri in manual if ri[1] == dm)
            if ri[2] is not None and r[2] is not None and ri[2] < r[2]:
                r = ri
                tag = "manual"
            manual.remove(ri)

        records.append((tag, r))

    for mi in manual:
        records.append(("manual", mi))

    for k, record in sorted(records, key=lambda r: r[1][1]):
        if k == "pressure":
            make_continuous_water_level(root, record)
        else:
            make_water_level(root, record)
    return etree.tostring(root)


def well_construction_xml(records):
    return make_xml("Casings", records, make_well_construction)


def lithology_xml(records):
    return make_xml("Lithologies", records, make_lithology)


def make_xml(name, records, make_record):
    root = etree.Element(name)
    # doc = etree.ElementTree(root)
    for r in records:
        make_record(root, r)

    # etree.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    # etree.register_namespace('xsd', 'http://www.w3.org/2001/XMLSchema')

    return etree.tostring(root)


# ==================== make records =======================
def make_continuous_water_level(root, r):
    """
    r is a transducer_daily_data row: (point_id, date_measured, depth_to_water_bgs)
    """
    elem = etree.SubElement(root, "WaterLevel")
    make_point_id(elem, r)

    m = r[1]

    for attr, val in (
        ("DepthFromLandSurfaceData", "{:0.2f}".format(r[2])),
        ("WaterLevelUnits", "ft bgs"),
        ("MeasuringMethod", "Pressure Transducer"),
        ("MeasurementMonth", m.month),
        ("MeasurementDay", m.day),
        ("MeasurementYear", m.year),
        ("MeasurementTime", "0:00:00"),
        ("MeasurementTimezone", "MST"),
        ("WaterLevelAccuracy", "0.02 ft"),
    ):
        e = etree.SubElement(elem, attr)
        e.text = _as_text(val)


def make_water_level(root, r):
    elem = etree.SubElement(root, "WaterLevel")
    make_point_id(elem, r)

    m = r[1]

    # m = datetime.strptime(m, '%Y-%m-%d')
    for attr, val in (
        ("DepthFromLandSurfaceData", "{:0.2f}".format(r[2])),
        ("WaterLevelUnits", r[3]),
        ("MeasuringMethod", r[4]),
        ("MeasurementMonth", m.month),
        ("MeasurementDay", m.day),
        ("MeasurementYear", m.year),
        ("MeasurementTime", "0:00:00"),
        ("MeasurementTimezone", "MST"),
        ("WaterLevelAccuracy", r[5]),
    ):
        e = etree.SubElement(elem, attr)
        e.text = _as_text(val)


def make_well_construction(root, r):
    """
    0        1         2             3          4          5            6               7                  8
    pointid, castop, casbottom, cadepthunits, screentop, screenbottom, screenbottomunit, screen description, casing description

    Element names and order follow the legacy AMPAPI feed that NGWMN
    harvests (AMPAPI routers/ngwmn/ngwmn_xml.py).
    """
    elem = etree.SubElement(root, "Casing")
    make_point_id(elem, r, idx=0)

    for tag, val in (
        ("CasingTop", r[1]),
        ("CasingBottom", r[2]),
        ("CasingDepthUnits", r[3]),
        ("ScreenTop", r[4]),
        ("ScreenBottom", r[5]),
        ("ScreenBottomUnits", r[6]),
        ("ScreenIntervalMaterial", r[7] or "Unknown"),
        ("CasingIntervalMaterial", r[8] or "Unknown"),
    ):
        e = etree.SubElement(elem, tag)
        e.text = _as_text(val)


def make_lithology(root, r):
    """
    0        1     2             3         4             5            6
    pointid, term, strat source, strattop, strattopunit, stratbottom, stratbottomunit

    Element names and order follow the legacy AMPAPI feed that NGWMN
    harvests. LithologyCode is the legacy LU_Lithology abbreviation, which
    the new model does not store, so it is recovered from the term.
    """
    elem = etree.SubElement(root, "Lithology")
    make_point_id(elem, r, idx=0)

    for tag, val in (
        ("LithologyCode", lithology_code(r[1])),
        ("TERM", r[1]),
        ("StratSource", r[2]),
        ("StratTop", r[3]),
        ("StratTopUnit", r[4]),
        ("StratBottom", r[5]),
        ("StratBottomUnit", r[6]),
    ):
        e = etree.SubElement(elem, tag)
        e.text = _as_text(val)


def make_point_id(elem, r, idx=0):
    e = etree.SubElement(elem, "PointID")
    v = r[idx]
    e.text = _as_text(v)
