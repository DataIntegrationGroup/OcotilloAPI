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
Legacy NM_Aquifer lithology codes.

``Stratigraphy.Lithology`` held a ``LU_Lithology`` abbreviation (``CLYE``); the
new model stores only the resolved lexicon term (``Clay, yellow``). NGWMN still
harvests the abbreviation as ``LithologyCode``, so the export maps the term
back. The table is one-to-one, which makes the reverse lookup exact.

This is the same table the stratigraphic-interval backfill
(``data_migrations/migrations/20261105_0001_backfill_stratigraphic_intervals``)
used. That migration keeps its own frozen copy; a test holds the two equal.
"""

LITHOLOGY_CODES: dict[str, str] = {
    "ALVM": "Alluvium",
    "ANDR": "Anhydrite",
    "ANDS": "Andesite",
    "ARKS": "Arkose",
    "BLDR": "Boulders",
    "BLSC": "Boulders, silt and clay",
    "BLSD": "Boulders and sand",
    "BNTN": "Bentonite",
    "BRCC": "Breccia",
    "BSLT": "Basalt",
    "CGLM": "Conglomerate",
    "CHLK": "Chalk",
    "CHRT": "Chert",
    "CLAY": "Clay",
    "CLCH": "Caliche",
    "CLCT": "Calcite",
    "CLRD": "Clay, red",
    "CLSD": "Clay, some sand",
    "CLSN": "Claystone",
    "CLYE": "Clay, yellow",
    "COAL": "Coal",
    "COBB": "Cobbles",
    "COSC": "Cobbles, silt and clay",
    "COSD": "Cobbles and sand",
    "DLMT": "Dolomite",
    "DLSH": "Dolomite and shale",
    "EVPR": "Evaporite",
    "GNSS": "Gneiss",
    "GPSM": "Gypsum",
    "GRBL": "Gravel and boulders",
    "GRCK": "Graywacke",
    "GRCL": "Gravel and clay",
    "GRCM": "Gravel, cemented",
    "GRDS": "Gravel, sand and silt",
    "GRGN": "Granite, gneiss",
    "GRNT": "Granite",
    "GRSC": "Gravel, silt and clay",
    "GRVL": "Gravel",
    "IGIN": "Ignesous, intrusive, undifferentiated",
    "IGNS": "Igneous undifferentiated",
    "LGNT": "Lignite",
    "LMDM": "Limestone and dolomite",
    "LMSD": "Limestone and sandstone, interbedded",
    "LMSH": "Limestone and shale",
    "LMSN": "Limestone",
    "LMSS": "Limestone, sandstone and shale",
    "MARL": "Marl",
    "MDSN": "Mudstone",
    "MMPC": "Metamorphic undifferentiated",
    "MRLS": "Marlstone",
    "NR": "No Recovery",
    "PEAT": "Peat",
    "QRTZ": "Quartzite",
    "RYLT": "Rhyolite",
    "SAND": "Sand",
    "SCST": "Schist",
    "SDCL": "Sand and clay",
    "SDCS": "Sand, silt and clay",
    "SDGL": "Sand and gravel",
    "SDSL": "Sandstone and shale",
    "SDST": "Sand and silt",
    "SGSC": "Sand, gravel, silt and clay",
    "SGVC": "Sand, gravel and clay",
    "SHLE": "Shale",
    "SILT": "Silt",
    "SLSH": "Siltstone and shale",
    "SLSN": "Siltstone",
    "SLTE": "Slate",
    "SNCL": "Sand, some clay",
    "SNDS": "Sandstone",
    "SSTG": "Sand, silt and gravel",
    "STCL": "Silt and clay",
    "SUSE": "Surficial sediment",
    "TRVR": "Travertine",
    "TUFF": "Tuff",
    "VLCC": "Volcanic undifferentiated",
}
_CODES_BY_TERM = {term.casefold(): code for code, term in LITHOLOGY_CODES.items()}


def lithology_code(term: str | None) -> str | None:
    """The legacy ``LU_Lithology`` abbreviation for a lithology term, or None."""
    if not term:
        return None
    return _CODES_BY_TERM.get(term.strip().casefold())
