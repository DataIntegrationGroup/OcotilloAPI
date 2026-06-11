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

from sqlalchemy import text


def _as_text(v):
    return "" if v is None else str(v)


# NSMAP = dict(xsi="http://www.w3.org/2001/XMLSchema-instance", xsd="http://www.w3.org/2001/XMLSchema")


def make_xml_response(db, sql, point_id, func):
    if not isinstance(sql, (tuple, list)):
        sql = (sql,)

    rs = []
    for si in sql:
        records = db.execute(text(si), {"point_id": point_id})
        rs.append(records.fetchall())
    return func(*rs)


def make_lithology_response(point_id, db):
    sql = (
        'select "PointID", "StratTop", "StratBottom", "TERM" '
        'from "view_NGWMN_Lithology" where "PointID"=:point_id'
    )
    return make_xml_response(db, sql, point_id, lithology_xml)


def make_well_construction_response(point_id, db):
    sql = (
        'select "PointID", "CasingTop", "CasingBottom", "CasingDepthUnits", '
        '"ScreenTop", "ScreenBottom", "ScreenBottomUnit", "ScreenDescription", "CasingDescription" '
        'from "view_NGWMN_WellConstruction" where "PointID"=:point_id'
    )
    return make_xml_response(db, sql, point_id, well_construction_xml)


def make_waterlevels_response(point_id, db):
    sql = (
        'select * from "view_NGWMN_WaterLevels" where "PointID"=:point_id '
        'order by "DateMeasured"'
    )
    sql2 = (
        "select point_id, date_measured, depth_to_water_bgs "
        "from transducer_daily_data "
        "where point_id=:point_id and qced is true "
        "and parameter_name='groundwater level' "
        "order by date_measured"
    )

    return make_xml_response(db, (sql, sql2), point_id, water_levels_xml2)


# ==================== make xml =======================
def continuous_water_levels_xml(records):
    return make_xml("WaterLevels", records, make_continuous_water_level)


def water_levels_xml(records):
    return make_xml("WaterLevels", records, make_water_level)


def water_levels_xml2(manual, pressure):
    """
    Merge manual measurements (view_NGWMN_WaterLevels rows) with daily
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
    :param root:
    :param r:
    :return:
    """
    elem = etree.SubElement(root, "Casing")
    make_point_id(elem, r, idx=0)

    e = etree.SubElement(elem, "CasingTop")
    e.text = _as_text(r[1])

    e = etree.SubElement(elem, "CasingBottom")
    e.text = _as_text(r[2])

    e = etree.SubElement(elem, "CasingDepthUnits")
    e.text = _as_text(r[3])

    e = etree.SubElement(elem, "ScreenTop")
    e.text = _as_text(r[4])

    e = etree.SubElement(elem, "ScreenBottom")
    e.text = _as_text(r[5])

    e = etree.SubElement(elem, "ScreenDescription")
    e.text = _as_text(r[7])

    e = etree.SubElement(elem, "ScreenMaterial")
    e.text = "steel"


def make_lithology(root, r):
    elem = etree.SubElement(root, "Lithology")
    make_point_id(elem, r, idx=0)

    e = etree.SubElement(elem, "TopDepth")
    e.text = _as_text(r[1])

    e = etree.SubElement(elem, "BottomDepth")
    e.text = _as_text(r[2])

    e = etree.SubElement(elem, "Units")
    e.text = "feet"

    e = etree.SubElement(elem, "Description")
    e.text = _as_text(r[3])


def make_point_id(elem, r, idx=0):
    e = etree.SubElement(elem, "PointID")
    v = r[idx]
    e.text = _as_text(v)
