# Contract Details

| **Item** | **Value** |
| --- | --- |
| Contract Version | 1.0.0 |
| Status | Accepted |
| Provider | OcotilloAPI |
| Consumers | WeaverAPI, public users |
| Standards | OGC API - EDR 1.1 (OGC 19-086r6), CoverageJSON (OGC 21-069r2), GeoJSON (RFC 7946) |
| Base path | `/ogcapi/collections/water_chemistry` |
| Authentication | None, public data only for `/ogcapi/...`. |

# Purpose
The purpose of this document is to determine and record the shape of the `/water_chemistryt` OGC EDR API endpoints. These endpoints will be used by external sources and so the schemas defined herein will act as the source of truth for how it will be shaped by OcotilloAPI and how it will be consumed by others (e.g. WeaverAPI).

# /water_chemistry

## Data
The data served by the `/water_chemistry` OGC EDR endpoints will consist of

- Well information and water chemistry observations.
- Public data for `/ogcapi/water_chemistry/` endpoints.
- Both real and `null` values, both of which contain corresponding reasons for their state.

### Shape

#### Sites

The sites will be returned as a FeatureCollection of [GeoJSONs](https://geojson.org/) as follows

```json
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": id,
            "geometry": {
                "type": "Point",
                "coordinates": [longitude, latitude]
            },
            "properties": {
                "name": name,
                "elevation": elevation,
                "elevation_units": "m",
                "horizontal_datum": "WGS84",
                "vertical_datum": "NAVD88",
                "well_depth": well_depth,
                "well_depth_units": "ft",
                "alternate_ids": [
                    {
                        "id": id,
                        "relation": relation,
                        "organization": organization
                    }
                ]
            }
        }
    ]
}
```

where

| **Field** | **Type** | **Description** |
| --- | --- | --- |
| `id` | `str` | Internal id of the well |
| `elevation` | `float` | Elevation of the well, in meters |
| `elevation_units` | `str` | Always `"m"` |
| `horizontal_datum` | `str` | Always `"WGS84"` |
| `vertical_datum` | `str` | Always `"NAVD88"` |
| `well_depth` | `float` or `null` | Depth of the well, in feet |
| `well_depth_units` | `str` | Always `"ft"` |
| `alternate_ids` | `list` | Alternate ids for the well. Each element is an object with `id`, `relation`, and `organization` |

#### Time series

The time series data will be returned as CoverageCollection of [CoverageJSONs](https://docs.ogc.org/cs/21-069r2/21-069r2.html) as follows

```json
{
    "type": "CoverageCollection",
    "domainType": "PointSeries",
    "parameters": {
        "3H": {
            "type": "Parameter",
            "description": {
                "en": "Tritium"
            },
            "observedProperty": {
                "id": "3H",
                "label": {
                    "en": "Tritium"
                }
            },
            "unit": {
                "symbol": "TU",
                "label": {
                    "en": "Tritium units"
                }
            }
        },
        "3H:3He Age": {
            "type": "Parameter",
            "description": {
                "en": "Age of Water using dissolved gases"
            },
            "observedProperty": {
                "id": "3H:3He Age",
                "label": {
                    "en": "Age of Water using dissolved gases"
                }
            },
            "unit": {
                "symbol": "yrs",
                "label": {
                    "en": "years"
                }
            }
        },
        "Ag": {
            "type": "Parameter",
            "description": {
                "en": "Silver"
            },
            "observedProperty": {
                "id": "Ag",
                "label": {
                    "en": "Silver"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ag(total)": {
            "type": "Parameter",
            "description": {
                "en": "Silver, total, unfiltered"
            },
            "observedProperty": {
                "id": "Ag(total)",
                "label": {
                    "en": "Silver, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Al": {
            "type": "Parameter",
            "description": {
                "en": "Aluminum"
            },
            "observedProperty": {
                "id": "Al",
                "label": {
                    "en": "Aluminum"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Al(total)": {
            "type": "Parameter",
            "description": {
                "en": "Aluminum, total, unfiltered"
            },
            "observedProperty": {
                "id": "Al(total)",
                "label": {
                    "en": "Aluminum, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "ALK": {
            "type": "Parameter",
            "description": {
                "en": "Alkalinity, Total"
            },
            "observedProperty": {
                "id": "ALK",
                "label": {
                    "en": "Alkalinity, Total"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "As": {
            "type": "Parameter",
            "description": {
                "en": "Arsenic"
            },
            "observedProperty": {
                "id": "As",
                "label": {
                    "en": "Arsenic"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "As(total)": {
            "type": "Parameter",
            "description": {
                "en": "Arsenic, total, unfiltered"
            },
            "observedProperty": {
                "id": "As(total)",
                "label": {
                    "en": "Arsenic, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "AsIII": {
            "type": "Parameter",
            "description": {
                "en": "Arsenite (arsenic species)"
            },
            "observedProperty": {
                "id": "AsIII",
                "label": {
                    "en": "Arsenite (arsenic species)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "AsV": {
            "type": "Parameter",
            "description": {
                "en": "Arsenate (arsenic species)"
            },
            "observedProperty": {
                "id": "AsV",
                "label": {
                    "en": "Arsenate (arsenic species)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "B": {
            "type": "Parameter",
            "description": {
                "en": "Boron"
            },
            "observedProperty": {
                "id": "B",
                "label": {
                    "en": "Boron"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "B(total)": {
            "type": "Parameter",
            "description": {
                "en": "Boron, total, unfiltered"
            },
            "observedProperty": {
                "id": "B(total)",
                "label": {
                    "en": "Boron, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ba": {
            "type": "Parameter",
            "description": {
                "en": "Barium"
            },
            "observedProperty": {
                "id": "Ba",
                "label": {
                    "en": "Barium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ba(total)": {
            "type": "Parameter",
            "description": {
                "en": "Barium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Ba(total)",
                "label": {
                    "en": "Barium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Be": {
            "type": "Parameter",
            "description": {
                "en": "Beryllium"
            },
            "observedProperty": {
                "id": "Be",
                "label": {
                    "en": "Beryllium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Be(total)": {
            "type": "Parameter",
            "description": {
                "en": "Beryllium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Be(total)",
                "label": {
                    "en": "Beryllium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Br": {
            "type": "Parameter",
            "description": {
                "en": "Bromide"
            },
            "observedProperty": {
                "id": "Br",
                "label": {
                    "en": "Bromide"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "C13r": {
            "type": "Parameter",
            "description": {
                "en": "13C:12C ratio"
            },
            "observedProperty": {
                "id": "C13r",
                "label": {
                    "en": "13C:12C ratio"
                }
            },
            "unit": {
                "symbol": "pm",
                "label": {
                    "en": "Per mil (o/oo) or parts per thousand"
                }
            }
        },
        "C14": {
            "type": "Parameter",
            "description": {
                "en": "14C content, pmc"
            },
            "observedProperty": {
                "id": "C14",
                "label": {
                    "en": "14C content, pmc"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "C14_corrected": {
            "type": "Parameter",
            "description": {
                "en": "Corrected C14 in years"
            },
            "observedProperty": {
                "id": "C14_corrected",
                "label": {
                    "en": "Corrected C14 in years"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "C14_years": {
            "type": "Parameter",
            "description": {
                "en": "Uncorrected C14 age"
            },
            "observedProperty": {
                "id": "C14_years",
                "label": {
                    "en": "Uncorrected C14 age"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ca": {
            "type": "Parameter",
            "description": {
                "en": "Calcium"
            },
            "observedProperty": {
                "id": "Ca",
                "label": {
                    "en": "Calcium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ca(total)": {
            "type": "Parameter",
            "description": {
                "en": "Calcium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Ca(total)",
                "label": {
                    "en": "Calcium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cd": {
            "type": "Parameter",
            "description": {
                "en": "Cadmium"
            },
            "observedProperty": {
                "id": "Cd",
                "label": {
                    "en": "Cadmium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cd(total)": {
            "type": "Parameter",
            "description": {
                "en": "Cadmium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Cd(total)",
                "label": {
                    "en": "Cadmium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CFC11": {
            "type": "Parameter",
            "description": {
                "en": "Chlorofluorocarbon-11 avg age"
            },
            "observedProperty": {
                "id": "CFC11",
                "label": {
                    "en": "Chlorofluorocarbon-11 avg age"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CFC113": {
            "type": "Parameter",
            "description": {
                "en": "Chlorofluorocarbon-113 avg age"
            },
            "observedProperty": {
                "id": "CFC113",
                "label": {
                    "en": "Chlorofluorocarbon-113 avg age"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CFC113_12": {
            "type": "Parameter",
            "description": {
                "en": "Chlorofluorocarbon-113/12 avg RATIO age"
            },
            "observedProperty": {
                "id": "CFC113_12",
                "label": {
                    "en": "Chlorofluorocarbon-113/12 avg RATIO age"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CFC12": {
            "type": "Parameter",
            "description": {
                "en": "Chlorofluorocarbon-12 avg age"
            },
            "observedProperty": {
                "id": "CFC12",
                "label": {
                    "en": "Chlorofluorocarbon-12 avg age"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cl": {
            "type": "Parameter",
            "description": {
                "en": "Chloride"
            },
            "observedProperty": {
                "id": "Cl",
                "label": {
                    "en": "Chloride"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CN6": {
            "type": "Parameter",
            "description": {
                "en": "Cyanide"
            },
            "observedProperty": {
                "id": "CN6",
                "label": {
                    "en": "Cyanide"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Co": {
            "type": "Parameter",
            "description": {
                "en": "Cobalt"
            },
            "observedProperty": {
                "id": "Co",
                "label": {
                    "en": "Cobalt"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Co(total)": {
            "type": "Parameter",
            "description": {
                "en": "Cobalt, total, unfiltered"
            },
            "observedProperty": {
                "id": "Co(total)",
                "label": {
                    "en": "Cobalt, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CO3": {
            "type": "Parameter",
            "description": {
                "en": "Carbonate"
            },
            "observedProperty": {
                "id": "CO3",
                "label": {
                    "en": "Carbonate"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "CONDLAB": {
            "type": "Parameter",
            "description": {
                "en": "Conductivity, laboratory (µS)"
            },
            "observedProperty": {
                "id": "CONDLAB",
                "label": {
                    "en": "Conductivity, laboratory (µS)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cr": {
            "type": "Parameter",
            "description": {
                "en": "Chromium"
            },
            "observedProperty": {
                "id": "Cr",
                "label": {
                    "en": "Chromium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cr(total)": {
            "type": "Parameter",
            "description": {
                "en": "Chromium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Cr(total)",
                "label": {
                    "en": "Chromium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cu": {
            "type": "Parameter",
            "description": {
                "en": "Copper"
            },
            "observedProperty": {
                "id": "Cu",
                "label": {
                    "en": "Copper"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Cu(total)": {
            "type": "Parameter",
            "description": {
                "en": "Copper, total, unfiltered"
            },
            "observedProperty": {
                "id": "Cu(total)",
                "label": {
                    "en": "Copper, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "d13C-DIC": {
            "type": "Parameter",
            "description": {
                "en": "delta C13 of dissolved inorganic carbon"
            },
            "observedProperty": {
                "id": "d13C-DIC",
                "label": {
                    "en": "delta C13 of dissolved inorganic carbon"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "d18O-SO4": {
            "type": "Parameter",
            "description": {
                "en": "delta O18 sulfate"
            },
            "observedProperty": {
                "id": "d18O-SO4",
                "label": {
                    "en": "delta O18 sulfate"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "d34S-SO4": {
            "type": "Parameter",
            "description": {
                "en": "Sulfate 34 isotope ratio"
            },
            "observedProperty": {
                "id": "d34S-SO4",
                "label": {
                    "en": "Sulfate 34 isotope ratio"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "DOC": {
            "type": "Parameter",
            "description": {
                "en": "Dissolved organic carbon"
            },
            "observedProperty": {
                "id": "DOC",
                "label": {
                    "en": "Dissolved organic carbon"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "ERT": {
            "type": "Parameter",
            "description": {
                "en": "Estimated recharge temperature"
            },
            "observedProperty": {
                "id": "ERT",
                "label": {
                    "en": "Estimated recharge temperature"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "F": {
            "type": "Parameter",
            "description": {
                "en": "Fluoride"
            },
            "observedProperty": {
                "id": "F",
                "label": {
                    "en": "Fluoride"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Fe": {
            "type": "Parameter",
            "description": {
                "en": "Iron"
            },
            "observedProperty": {
                "id": "Fe",
                "label": {
                    "en": "Iron"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Fe(total)": {
            "type": "Parameter",
            "description": {
                "en": "Iron, total, unfiltered"
            },
            "observedProperty": {
                "id": "Fe(total)",
                "label": {
                    "en": "Iron, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "H2r": {
            "type": "Parameter",
            "description": {
                "en": "Deuterium:Hydrogen ratio"
            },
            "observedProperty": {
                "id": "H2r",
                "label": {
                    "en": "Deuterium:Hydrogen ratio"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "H2S": {
            "type": "Parameter",
            "description": {
                "en": "Hydrogen sulfide"
            },
            "observedProperty": {
                "id": "H2S",
                "label": {
                    "en": "Hydrogen sulfide"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "HCO3": {
            "type": "Parameter",
            "description": {
                "en": "Bicarbonate"
            },
            "observedProperty": {
                "id": "HCO3",
                "label": {
                    "en": "Bicarbonate"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Hg": {
            "type": "Parameter",
            "description": {
                "en": "Mercury"
            },
            "observedProperty": {
                "id": "Hg",
                "label": {
                    "en": "Mercury"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Hg(total)": {
            "type": "Parameter",
            "description": {
                "en": "Mercury, total, unfiltered"
            },
            "observedProperty": {
                "id": "Hg(total)",
                "label": {
                    "en": "Mercury, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "HRD": {
            "type": "Parameter",
            "description": {
                "en": "Hardness (CaCO3)"
            },
            "observedProperty": {
                "id": "HRD",
                "label": {
                    "en": "Hardness (CaCO3)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "IONBAL": {
            "type": "Parameter",
            "description": {
                "en": "Ion Balance"
            },
            "observedProperty": {
                "id": "IONBAL",
                "label": {
                    "en": "Ion Balance"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "K": {
            "type": "Parameter",
            "description": {
                "en": "Potassium"
            },
            "observedProperty": {
                "id": "K",
                "label": {
                    "en": "Potassium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "K(total)": {
            "type": "Parameter",
            "description": {
                "en": "Potassium, total, unfiltered"
            },
            "observedProperty": {
                "id": "K(total)",
                "label": {
                    "en": "Potassium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Li": {
            "type": "Parameter",
            "description": {
                "en": "Lithium"
            },
            "observedProperty": {
                "id": "Li",
                "label": {
                    "en": "Lithium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Li(total)": {
            "type": "Parameter",
            "description": {
                "en": "Lithium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Li(total)",
                "label": {
                    "en": "Lithium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mg": {
            "type": "Parameter",
            "description": {
                "en": "Magnesium"
            },
            "observedProperty": {
                "id": "Mg",
                "label": {
                    "en": "Magnesium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mg(total)": {
            "type": "Parameter",
            "description": {
                "en": "Magnesium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Mg(total)",
                "label": {
                    "en": "Magnesium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mn": {
            "type": "Parameter",
            "description": {
                "en": "Manganese"
            },
            "observedProperty": {
                "id": "Mn",
                "label": {
                    "en": "Manganese"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mn(total)": {
            "type": "Parameter",
            "description": {
                "en": "Manganese, total, unfiltered"
            },
            "observedProperty": {
                "id": "Mn(total)",
                "label": {
                    "en": "Manganese, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mo": {
            "type": "Parameter",
            "description": {
                "en": "Molybdenum"
            },
            "observedProperty": {
                "id": "Mo",
                "label": {
                    "en": "Molybdenum"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Mo(total)": {
            "type": "Parameter",
            "description": {
                "en": "Molybdenum, total, unfiltered"
            },
            "observedProperty": {
                "id": "Mo(total)",
                "label": {
                    "en": "Molybdenum, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Na": {
            "type": "Parameter",
            "description": {
                "en": "Sodium"
            },
            "observedProperty": {
                "id": "Na",
                "label": {
                    "en": "Sodium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Na(total)": {
            "type": "Parameter",
            "description": {
                "en": "Sodium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Na(total)",
                "label": {
                    "en": "Sodium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Na+K": {
            "type": "Parameter",
            "description": {
                "en": "Sodium and Potassium combined"
            },
            "observedProperty": {
                "id": "Na+K",
                "label": {
                    "en": "Sodium and Potassium combined"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NH3": {
            "type": "Parameter",
            "description": {
                "en": "Ammonia"
            },
            "observedProperty": {
                "id": "NH3",
                "label": {
                    "en": "Ammonia"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NH4": {
            "type": "Parameter",
            "description": {
                "en": "Ammonium"
            },
            "observedProperty": {
                "id": "NH4",
                "label": {
                    "en": "Ammonium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ni": {
            "type": "Parameter",
            "description": {
                "en": "Nickel"
            },
            "observedProperty": {
                "id": "Ni",
                "label": {
                    "en": "Nickel"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ni(total)": {
            "type": "Parameter",
            "description": {
                "en": "Nickel, total, unfiltered"
            },
            "observedProperty": {
                "id": "Ni(total)",
                "label": {
                    "en": "Nickel, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NO2": {
            "type": "Parameter",
            "description": {
                "en": "Nitrite (as NO2)"
            },
            "observedProperty": {
                "id": "NO2",
                "label": {
                    "en": "Nitrite (as NO2)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NO2(N)": {
            "type": "Parameter",
            "description": {
                "en": "Nitrite (as N)"
            },
            "observedProperty": {
                "id": "NO2(N)",
                "label": {
                    "en": "Nitrite (as N)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NO3": {
            "type": "Parameter",
            "description": {
                "en": "Nitrate (as NO3)"
            },
            "observedProperty": {
                "id": "NO3",
                "label": {
                    "en": "Nitrate (as NO3)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "NO3(N)": {
            "type": "Parameter",
            "description": {
                "en": "Nitrate (as N)"
            },
            "observedProperty": {
                "id": "NO3(N)",
                "label": {
                    "en": "Nitrate (as N)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "O18r": {
            "type": "Parameter",
            "description": {
                "en": "18O:16O ratio"
            },
            "observedProperty": {
                "id": "O18r",
                "label": {
                    "en": "18O:16O ratio"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "OH": {
            "type": "Parameter",
            "description": {
                "en": "Alkalinity as OH-"
            },
            "observedProperty": {
                "id": "OH",
                "label": {
                    "en": "Alkalinity as OH-"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Pb": {
            "type": "Parameter",
            "description": {
                "en": "Lead"
            },
            "observedProperty": {
                "id": "Pb",
                "label": {
                    "en": "Lead"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Pb(total)": {
            "type": "Parameter",
            "description": {
                "en": "Lead, total, unfiltered"
            },
            "observedProperty": {
                "id": "Pb(total)",
                "label": {
                    "en": "Lead, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "pHL": {
            "type": "Parameter",
            "description": {
                "en": "pH,laboratory"
            },
            "observedProperty": {
                "id": "pHL",
                "label": {
                    "en": "pH,laboratory"
                }
            },
            "unit": {
                "symbol": "dimensionless",
                "label": {
                    "en": "dimensionless"
                }
            }
        },
        "PO4": {
            "type": "Parameter",
            "description": {
                "en": "Phosphate"
            },
            "observedProperty": {
                "id": "PO4",
                "label": {
                    "en": "Phosphate"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sb": {
            "type": "Parameter",
            "description": {
                "en": "Antimony"
            },
            "observedProperty": {
                "id": "Sb",
                "label": {
                    "en": "Antimony"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sb(total)": {
            "type": "Parameter",
            "description": {
                "en": "Antimony, total, unfiltered"
            },
            "observedProperty": {
                "id": "Sb(total)",
                "label": {
                    "en": "Antimony, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Se": {
            "type": "Parameter",
            "description": {
                "en": "Selenium"
            },
            "observedProperty": {
                "id": "Se",
                "label": {
                    "en": "Selenium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Se(total)": {
            "type": "Parameter",
            "description": {
                "en": "Selenium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Se(total)",
                "label": {
                    "en": "Selenium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sf6": {
            "type": "Parameter",
            "description": {
                "en": "Sulfur hexafluoride"
            },
            "observedProperty": {
                "id": "Sf6",
                "label": {
                    "en": "Sulfur hexafluoride"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Si": {
            "type": "Parameter",
            "description": {
                "en": "Silicon"
            },
            "observedProperty": {
                "id": "Si",
                "label": {
                    "en": "Silicon"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Si(total)": {
            "type": "Parameter",
            "description": {
                "en": "Silicon, total, unfiltered"
            },
            "observedProperty": {
                "id": "Si(total)",
                "label": {
                    "en": "Silicon, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "SiO2": {
            "type": "Parameter",
            "description": {
                "en": "Silica"
            },
            "observedProperty": {
                "id": "SiO2",
                "label": {
                    "en": "Silica"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sn": {
            "type": "Parameter",
            "description": {
                "en": "Tin"
            },
            "observedProperty": {
                "id": "Sn",
                "label": {
                    "en": "Tin"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sn(total)": {
            "type": "Parameter",
            "description": {
                "en": "Tin, total, unfiltered"
            },
            "observedProperty": {
                "id": "Sn(total)",
                "label": {
                    "en": "Tin, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "SO4": {
            "type": "Parameter",
            "description": {
                "en": "Sulfate"
            },
            "observedProperty": {
                "id": "SO4",
                "label": {
                    "en": "Sulfate"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sr": {
            "type": "Parameter",
            "description": {
                "en": "Strontium"
            },
            "observedProperty": {
                "id": "Sr",
                "label": {
                    "en": "Strontium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sr(total)": {
            "type": "Parameter",
            "description": {
                "en": "Strontium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Sr(total)",
                "label": {
                    "en": "Strontium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Sr87:Sr86": {
            "type": "Parameter",
            "description": {
                "en": "Strontium 87:86 ratio"
            },
            "observedProperty": {
                "id": "Sr87:Sr86",
                "label": {
                    "en": "Strontium 87:86 ratio"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TAn": {
            "type": "Parameter",
            "description": {
                "en": "Total Anions"
            },
            "observedProperty": {
                "id": "TAn",
                "label": {
                    "en": "Total Anions"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TCat": {
            "type": "Parameter",
            "description": {
                "en": "Total Cations"
            },
            "observedProperty": {
                "id": "TCat",
                "label": {
                    "en": "Total Cations"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TDS": {
            "type": "Parameter",
            "description": {
                "en": "Total Dissolved Solids"
            },
            "observedProperty": {
                "id": "TDS",
                "label": {
                    "en": "Total Dissolved Solids"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Th": {
            "type": "Parameter",
            "description": {
                "en": "Thorium"
            },
            "observedProperty": {
                "id": "Th",
                "label": {
                    "en": "Thorium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Th(total)": {
            "type": "Parameter",
            "description": {
                "en": "Thorium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Th(total)",
                "label": {
                    "en": "Thorium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ti": {
            "type": "Parameter",
            "description": {
                "en": "Titanium"
            },
            "observedProperty": {
                "id": "Ti",
                "label": {
                    "en": "Titanium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Ti(total)": {
            "type": "Parameter",
            "description": {
                "en": "Titanium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Ti(total)",
                "label": {
                    "en": "Titanium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TKN": {
            "type": "Parameter",
            "description": {
                "en": "Total Kjeldahl nitrogen"
            },
            "observedProperty": {
                "id": "TKN",
                "label": {
                    "en": "Total Kjeldahl nitrogen"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Tl": {
            "type": "Parameter",
            "description": {
                "en": "Thallium"
            },
            "observedProperty": {
                "id": "Tl",
                "label": {
                    "en": "Thallium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Tl(total)": {
            "type": "Parameter",
            "description": {
                "en": "Thallium, total, unfiltered"
            },
            "observedProperty": {
                "id": "Tl(total)",
                "label": {
                    "en": "Thallium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TN": {
            "type": "Parameter",
            "description": {
                "en": "Total nitrogen"
            },
            "observedProperty": {
                "id": "TN",
                "label": {
                    "en": "Total nitrogen"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "TOC": {
            "type": "Parameter",
            "description": {
                "en": "Total organic carbon"
            },
            "observedProperty": {
                "id": "TOC",
                "label": {
                    "en": "Total organic carbon"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "U": {
            "type": "Parameter",
            "description": {
                "en": "Uranium (total, by ICP-MS)"
            },
            "observedProperty": {
                "id": "U",
                "label": {
                    "en": "Uranium (total, by ICP-MS)"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "U(total)": {
            "type": "Parameter",
            "description": {
                "en": "Uranium, total, unfiltered"
            },
            "observedProperty": {
                "id": "U(total)",
                "label": {
                    "en": "Uranium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "V": {
            "type": "Parameter",
            "description": {
                "en": "Vanadium"
            },
            "observedProperty": {
                "id": "V",
                "label": {
                    "en": "Vanadium"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "V(total)": {
            "type": "Parameter",
            "description": {
                "en": "Vanadium, total, unfiltered"
            },
            "observedProperty": {
                "id": "V(total)",
                "label": {
                    "en": "Vanadium, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Zn": {
            "type": "Parameter",
            "description": {
                "en": "Zinc"
            },
            "observedProperty": {
                "id": "Zn",
                "label": {
                    "en": "Zinc"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        },
        "Zn(total)": {
            "type": "Parameter",
            "description": {
                "en": "Zinc, total, unfiltered"
            },
            "observedProperty": {
                "id": "Zn(total)",
                "label": {
                    "en": "Zinc, total, unfiltered"
                }
            },
            "unit": {
                "symbol": "mg/L",
                "label": {
                    "en": "mg/L"
                }
            }
        }
    },
    "coverages": [
        {
            "type": "Coverage",
            "id": id,
            "domain": {
                "type": "Domain",
                "domainType": "PointSeries",
                "axes": {
                    "x": {
                        "values": [longitude]
                    },
                    "y": {
                        "values": [latitude]
                    },
                    "t": {
                        "values": [value 1 datetime, value 2 datetime, ..., value n datetime]
                    }
                },
                "referencing": [
                    {
                        "coordinates": ["x", "y"],
                        "system": {
                            "type": "GeographicCRS",
                            "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                        }
                    },
                    {
                        "coordinates": ["t"],
                        "system": {
                            "type": "TemporalRS",
                            "calendar": "Gregorian"
                        }
                    }
                ]
            },
            "ranges": {
                "groundwater level below ground surface": {
                    "type": "NdArray",
                    "dataType": "float",
                    "axisNames": ["t"],
                    "shape": [n],
                    "values": [value 1, value 2, ..., value n]
                },
                "groundwater level reason": {
                    "type": "NdArray",
                    "dataType": "string",
                    "axisNames": ["t"],
                    "shape": [n],
                    "values": [value 1 reason, value 2 reason, ..., value n reason]
                }
            }
        }
    ]
}
```

# Notes

## ogc_waterchemistry view

The following fields will need to be changed/coerced (using an if statement?) since they differ from the keys in the parameters. This is because the `parameter-name` query parameter is provided as a comma-separated list, so the names can't contain commas.

- 

## EDR Formation/Construction

- the `observedProperty` no longer corresponds with the key, so the edr_provider needs to be updated

# Outstanding questions

- What should we do for the `id` in the observedProperty? Is there a URL we can link to? Some other suggestion?