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
A PostgreSQL-backed OGC API - EDR provider for pygeoapi (see ADR3).

pygeoapi's bundled EDR providers target gridded/xarray data. Ocotillo's
observational data is relational point/time-series, so this provider serves
CoverageJSON directly from the publication-filtered ``ogc_manual_waterlevels`` and
``ogc_water_chemistry`` views.

Each backing view is a flat table with one row per reading. Every view has the
station columns::

    id, thing_id, thing_type, name, longitude, latitude, release_status

plus the independent-axis column the collection names in ``independent_axis``
(``{"axis": "t", "column": "datetime"}`` for a time series), and optionally:

    thing_type        station kind, published on /locations when present
    <instance_field>  e.g. a deployment id, exposed as EDR instances

Parameters are not fixed columns. Each entry in the collection's
``parameter_columns`` names a group of columns that carries one parameter value
per row::

    name_column       the parameter's name, read from the data (SELECT DISTINCT)
    value_column      its value, of the entry's data_type (float/integer/string)
    unit_column       its unit, or None for a parameter without one
    lexicon_category  for a categorical parameter, the lexicon category whose
                      terms are its allowed values (published as CoverageJSON
                      categories); None otherwise

so a view can carry several parameters on one row (wide), many parameters down
one name column (long), or both. ``ogc_manual_waterlevels``, for example::

    observation_parameter_name  'groundwater level below ground surface'
    observation_value           value - COALESCE(measuring_point_height, 0)
    observation_unit            'ft'
    qualifier_parameter_name    'groundwater level reason'
    qualifier_value             groundwater_level_reason
    (no unit column)

Rules the views must follow:

- emit the name on every row that carries the parameter, even when the value
  is null, or discovery can miss the parameter entirely; a null name means
  the row carries nothing for that entry;
- a name appears in only one ``parameter_columns`` entry, with one unit.

The provider groups rows by station (``thing_id``) into one CoverageJSON
coverage each, with one range per parameter along the independent axis.
Parameters on the same row share an axis index. Only a time axis
(``PointSeries``) is supported today.
"""

import logging
import os
import re
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from pygeoapi.provider.base import (
    ProviderConnectionError,
    ProviderNoDataError,
)
from pygeoapi.provider.base_edr import BaseEDRProvider

from core.ogc_field_metadata import describe_fields, table_entries

LOGGER = logging.getLogger(__name__)

GEOGRAPHIC_CRS = {
    "coordinates": ["x", "y"],
    "system": {
        "type": "GeographicCRS",
        "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
    },
}

TEMPORAL_RS = {
    "coordinates": ["t"],
    "system": {"type": "TemporalRS", "calendar": "Gregorian"},
}

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def _expand_env(value):
    """Expand ``${VAR}`` references in a config value using the environment."""
    if not isinstance(value, str):
        return value
    return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)


def categories_from_lexicon(rows):
    """CoverageJSON categories from lexicon ``term``/``definition`` rows.

    Each category's id and label are the term. A description is added only
    where the definition says more than the term itself; many lexicon terms
    are their own definition, and repeating them adds nothing.
    """
    categories = []
    for row in rows:
        term, definition = row["term"], row["definition"]
        category = {"id": term, "label": {"en": term}}
        if definition and definition != term:
            category["description"] = {"en": definition}
        categories.append(category)
    return categories


class StationEDRProvider(BaseEDRProvider):
    """EDR provider serving CoverageJSON from a flat ogc_* readings view."""

    def __init__(self, provider_def):
        super().__init__(provider_def)

        data = provider_def.get("data", {})
        self._conn_args = {
            "host": _expand_env(data.get("host", "localhost")),
            "port": int(_expand_env(str(data.get("port", 5432)))),
            "dbname": _expand_env(data.get("dbname", "postgres")),
            "user": _expand_env(data.get("user", "")),
            "password": _expand_env(data.get("password", "")),
        }
        # The backing view is a trusted, config-supplied identifier.
        self.table = provider_def["table"]
        self.id_field = provider_def["id_field"]
        self.parameter_columns = provider_def["parameter_columns"]
        self.station_properties = provider_def["station_properties"]
        self.independent_axis = provider_def["independent_axis"]["axis"]
        self.independent_axis_column_name = provider_def["independent_axis"]["column"]

        # optional - .get defaults to None if not present
        self.instance_field = provider_def.get("instance_field")

        if self.independent_axis == "t":
            self.domain_type = "PointSeries"
            self.independent_axis_transformer = datetime.isoformat
            self.referencing = [GEOGRAPHIC_CRS, TEMPORAL_RS]
        else:
            # Only "t" (time) is currently supported as the independent axis.
            # Future support for other independent axes (e.g., vertical "z") may be added here.
            raise ValueError(f"Unsupported independent axis: {self.independent_axis}")

        self._fields = {}
        # parameter name -> CoverageJSON categories, for categorical parameters.
        # Filled by get_fields during discovery, since names come from the data.
        self._lexicon_categories = {}
        self.get_fields()

    # ------------------------------------------------------------------ db
    def _connect(self):
        try:
            return psycopg2.connect(cursor_factory=RealDictCursor, **self._conn_args)
        except psycopg2.Error as err:
            LOGGER.error(f"EDR provider connection error: {err}")
            raise ProviderConnectionError(str(err))

    def _fetch(self, sql, params=None):
        conn = None
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                return cur.fetchall()
        except psycopg2.Error as err:
            LOGGER.error(f"EDR provider query error: {err}")
            raise ProviderConnectionError(str(err))
        finally:
            if conn is not None:
                conn.close()

    def _has_column(self, column):
        """Whether the backing relation exposes ``column``.

        Reads pg_attribute rather than information_schema.columns: the
        chemistry collections are backed by materialized views, which
        information_schema does not list at all.
        """
        try:
            rows = self._fetch(
                "SELECT 1 FROM pg_attribute "
                "WHERE attrelid = to_regclass(%s) AND attname = %s "
                "AND attnum > 0 AND NOT attisdropped LIMIT 1",
                [self.table, column],
            )
        except ProviderConnectionError:
            # View may not exist yet (e.g. OpenAPI generation before migrate).
            return False
        return bool(rows)

    # -------------------------------------------------------------- fields
    def get_fields(self):
        """Return the parameter-name fields present in the backing view.

        In an EDR provider ``fields`` are the parameters, not the supporting view's
        columns in the database.

        Each call hands back fresh per-field dicts. pygeoapi's
        get_collection_schema mutates what a provider returns in place --
        popping ``format``, assigning ``x-ogc-role`` -- so returning the
        cached dicts themselves would let one request's edits accumulate on
        the next one's response.
        """
        if self._fields:
            return {name: dict(field) for name, field in self._fields.items()}

        fields = {}
        lexicon_categories = {}  # parameter name -> CoverageJSON categories

        # The fetched dict is the per-category cache, so chemistry qualifiers sharing a category cost one query.
        fetched = {}  # lexicon category -> categories, so each is queried once
        for spec in self.parameter_columns:
            name_column = spec["name_column"]
            unit_column = spec["unit_column"] if spec["unit_column"] else "NULL"
            data_type = spec["data_type"]
            lexicon_category = spec["lexicon_category"]

            try:
                rows = self._fetch(
                    f"SELECT DISTINCT {name_column} AS parameter_name, {unit_column} AS unit "
                    f"FROM {self.table} WHERE {name_column} IS NOT NULL ORDER BY {name_column}"
                )
                if lexicon_category and rows and lexicon_category not in fetched:
                    fetched[lexicon_category] = self._create_lexicon_categories(
                        lexicon_category
                    )
            except ProviderConnectionError:
                # View may not exist yet (e.g. OpenAPI generation before migrate).
                return {}

            for row in rows:
                parameter_name = row["parameter_name"]
                if (
                    parameter_name in fields
                    and fields[parameter_name].get("x-ogc-unit") != row["unit"]
                ):
                    raise ValueError(  # R13
                        f"{self.table}: parameter {parameter_name!r} has more than one unit"
                    )

                fields[parameter_name] = {
                    "type": data_type,
                    "title": parameter_name,
                    "description": parameter_name,
                }

                if row["unit"] is not None:
                    fields[parameter_name]["x-ogc-unit"] = row["unit"]

                # a categorical parameter's allowed values: categories for
                # CoverageJSON and parameter_names, enum for /schema. Names
                # sharing a lexicon category share one list.
                if lexicon_category:
                    categories = fetched[lexicon_category]
                    lexicon_categories[parameter_name] = categories
                    fields[parameter_name]["enum"] = [c["id"] for c in categories]

        # Same prose source as the feature collections, keyed by parameter
        # name rather than column name. Parameter names are read out of the
        # data, so an undocumented analyte keeps its generated title.
        self._lexicon_categories = lexicon_categories
        self._fields = describe_fields(self.table, fields)
        return {name: dict(field) for name, field in self._fields.items()}

    @property
    def fields(self):
        return self.get_fields()

    def get_parameters(self, parameters=None, as_list=False):
        """EDR parameter metadata for the collection page (``parameter_names``).

        Overrides BaseEDRProvider.get_parameters, which reads
        ``field["x-ogc-unit"]`` unconditionally: a parameter without a unit,
        like a categorical qualifier, would raise KeyError and 500 the
        collection page. Here ``unit`` is published only when the field has
        one, matching the CoverageJSON parameters block.
        """
        fields = self.fields  # one call: each access builds fresh copies
        names = list(parameters) if parameters else list(fields)

        out_params = {}
        for name in names:
            field = fields[name]
            label = field.get("title", name)
            parameter = {
                "id": name,
                "type": "Parameter",
                "name": label,
                "observedProperty": {"id": name, "label": {"en": label}},
            }
            if field.get("description") is not None:
                parameter["observedProperty"]["description"] = {
                    "en": field["description"]
                }
            if field.get("x-ogc-unit") is not None:
                parameter["unit"] = {
                    "symbol": {
                        "value": field["x-ogc-unit"],
                        "type": "http://www.opengis.net/def/uom/UCUM/",
                    }
                }
            if name in self._lexicon_categories:
                parameter["observedProperty"]["categories"] = self._lexicon_categories[
                    name
                ]
            out_params[name] = parameter

        return list(out_params.values()) if as_list else out_params

    # ----------------------------------------------------------- instances
    def instances(self):
        """List transducer-deployment instance identifiers.

        Named for pygeoapi's EDR contract, not ours: ``get_collection_edr_
        instances`` calls ``p.instances()`` and ``p.instance(id)``, and
        ``BaseEDRProvider`` *returns* (rather than raises) a
        ``NotImplementedError`` instance from both. A provider that spells
        these ``get_instances``/``get_instance`` therefore does not override
        anything -- /instances iterates the NotImplementedError object and
        500s, and /instances/{id}/... validates against a truthy object, so
        any id at all is accepted.
        """
        if not self.instance_field:
            return []
        rows = self._fetch(
            f"SELECT DISTINCT {self.instance_field} AS iid "  # noqa: S608
            f"FROM {self.table} WHERE {self.instance_field} IS NOT NULL "
            f"ORDER BY {self.instance_field}"
        )
        return [str(row["iid"]) for row in rows]

    def instance(self, instance):
        """Validate an instance identifier."""
        return str(instance) in set(self.instances())

    # ------------------------------------------------------------ queries
    def locations(
        self,
        select_properties=None,
        datetime_=None,
        location_id=None,
        instance=None,
        bbox=None,
        **kwargs,
    ):
        """
        EDR locations query.

        With ``location_id`` set, return a CoverageJSON CoverageCollection for
        that station; otherwise return a GeoJSON FeatureCollection of the
        stations that have data.
        """
        if location_id is not None:
            rows = self._read(
                thing_id=location_id,
                datetime_=datetime_,
                select_properties=select_properties,
                instance=instance,
            )
            return self._coverage_collection(rows, select_properties=select_properties)

        # location listing: one feature per station with data
        clauses, params = self._filters(
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
            bbox=bbox,
        )

        non_specific_station_columns = [
            "thing_id",
            "thing_type",
            "name",
            "longitude",
            "latitude",
        ]
        specific_station_columns = [
            c for c in self.station_properties if c not in non_specific_station_columns
        ]
        columns = ", ".join(non_specific_station_columns + specific_station_columns)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._fetch(
            f"SELECT DISTINCT ON (thing_id) {columns} "  # noqa: S608 (trusted table/columns)
            f"FROM {self.table}{where} "
            "ORDER BY thing_id",
            params,
        )
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": row["thing_id"],
                    "geometry": {
                        "type": "Point",
                        "coordinates": [row["longitude"], row["latitude"]],
                    },
                    "properties": self._station_properties(row),
                }
                for row in rows
            ],
        }

    def _station_properties(self, row):
        """GeoJSON properties for one station on /locations.

        Each column in the collection's ``station_properties`` config is
        published under its own name.
        """
        return {column: row[column] for column in self.station_properties}

    def area(
        self, wkt=None, select_properties=None, datetime_=None, instance=None, **kwargs
    ):
        """EDR area query: coverages for stations within a WKT polygon."""
        rows = self._read(
            wkt=wkt,
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
        )
        return self._coverage_collection(rows, select_properties=select_properties)

    def position(
        self, wkt=None, select_properties=None, datetime_=None, instance=None, **kwargs
    ):
        """EDR position query: coverages for stations intersecting the WKT."""
        rows = self._read(
            wkt=wkt,
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
        )
        return self._coverage_collection(rows, select_properties=select_properties)

    def cube(
        self, bbox=None, select_properties=None, datetime_=None, instance=None, **kwargs
    ):
        """EDR cube query: coverages for stations within a bbox."""
        rows = self._read(
            bbox=bbox,
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
        )
        return self._coverage_collection(rows, select_properties=select_properties)

    # --------------------------------------------------------- read/filter
    """
    Developer's notes:
    datetime_ filters the axis column, which for a time series (axis "t") is
    the time column. pygeoapi also passes the EDR `z` parameter, which arrives
    in the query methods' **kwargs and is ignored, as the water-level contract
    says. When a vertical-profile collection (axis "z") is added:
      - thread z through locations/area/position/cube -> _read -> _filters;
      - z filters the axis column (depth/elevation);
      - datetime_ must filter the profile's own time column instead, not the
        axis -- add a separate time column to independent_axis config;
      - coverages group by station + profile, not station alone.

    """

    def _filters(
        self, datetime_=None, select_properties=None, instance=None, bbox=None, wkt=None
    ):
        clauses = []
        params = []
        if datetime_:
            start, end = self._parse_interval(datetime_)
            if start is not None:
                clauses.append(f"{self.independent_axis_column_name} >= %s")
                params.append(start)
            if end is not None:
                clauses.append(f"{self.independent_axis_column_name} <= %s")
                params.append(end)
        if select_properties:
            names = list(select_properties)
            clauses.append(
                "("
                + " OR ".join(
                    f"{s['name_column']} = ANY(%s)" for s in self.parameter_columns
                )
                + ")"
            )
            params.extend([names] * len(self.parameter_columns))
        if instance and self.instance_field:
            clauses.append(f"{self.instance_field} = %s")
            params.append(instance)
        if bbox:
            clauses.append("longitude BETWEEN %s AND %s AND latitude BETWEEN %s AND %s")
            params.extend([bbox[0], bbox[2], bbox[1], bbox[3]])
        if wkt is not None:
            clauses.append(
                "ST_Intersects("
                "ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), "
                "ST_GeomFromText(%s, 4326))"
            )
            params.append(wkt.wkt if hasattr(wkt, "wkt") else str(wkt))
        return clauses, params

    def _read(
        self,
        thing_id=None,
        wkt=None,
        bbox=None,
        datetime_=None,
        select_properties=None,
        instance=None,
    ):
        clauses, params = self._filters(
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
            bbox=bbox,
            wkt=wkt,
        )
        if thing_id is not None:
            clauses.append("thing_id = %s")
            params.append(thing_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        columns = [
            "thing_id",
            "longitude",
            "latitude",
            self.independent_axis_column_name,
        ]
        for parameter_column_set in self.parameter_columns:
            for key in ("name_column", "value_column", "unit_column"):
                column = parameter_column_set[key]
                if column is not None and column not in columns:
                    columns.append(column)

        return self._fetch(
            f"SELECT {', '.join(columns)} "  # noqa: S608 (trusted, config-supplied columns)
            f"FROM {self.table}{where} "
            f"ORDER BY thing_id, {self.independent_axis_column_name}",
            params,
        )

    # ------------------------------------------------------- coveragejson
    def _parameter_documentation(self, parameter_name):
        """Documented title/description for one EDR parameter, or ``{}``."""
        return table_entries(self.table).get(parameter_name, {})

    def _coverage_collection(self, rows, select_properties=None):
        if not rows:
            raise ProviderNoDataError("No data found")

        # only keep the selected properties if specified
        selected_properties = set(select_properties) if select_properties else None

        # collect unique parameter metadata, where a parameter is assumed to always have the same unit
        # if a unit exists for that parameter
        parameters = {}
        stations = {}
        for row in rows:
            stations.setdefault(row["thing_id"], []).append(row)
            for parameter_column_set in self.parameter_columns:
                name = row[parameter_column_set["name_column"]]

                if name is None or (
                    selected_properties is not None and name not in selected_properties
                ):
                    continue

                if name not in parameters:
                    # A CoverageJSON client reads observedProperty.label for the
                    # display name and description for the explanation; both were
                    # the raw parameter name before the field metadata existed.
                    entry = self._parameter_documentation(name)
                    parameters[name] = {
                        "type": "Parameter",
                        "description": {"en": entry.get("description", name)},
                        "observedProperty": {
                            "id": name,
                            "label": {"en": entry.get("title", name)},
                        },
                    }

                    # a categorical parameter lists its allowed values. .get, not
                    # [name]: a name added to the view after discovery ran has
                    # no entry, and is published without categories.
                    categories = self._lexicon_categories.get(name)
                    if categories is not None:
                        parameters[name]["observedProperty"]["categories"] = categories

                    # not every parameter has a unit, so leave it out if it is None
                    if parameter_column_set["unit_column"] is not None:
                        parameters[name]["unit"] = {
                            "symbol": row[parameter_column_set["unit_column"]],
                            "label": {"en": row[parameter_column_set["unit_column"]]},
                        }

        # build the coverage for each station, one at a time
        coverages = []
        for thing_id, station_rows in stations.items():
            lon = station_rows[0]["longitude"]
            lat = station_rows[0]["latitude"]

            # union of independent axis - e.g. timestamp or vertical depth - across params for this station
            independent_axis_raw_values = sorted(
                {r[self.independent_axis_column_name] for r in station_rows}
            )

            # used to look up the data with the raw independent axis values since transformed
            # values may not work (e.g. after converting timestamps to ISO format)
            independent_axis_index = {
                raw_value: i for i, raw_value in enumerate(independent_axis_raw_values)
            }

            # one range per parameter where each range's values are the same length
            # (meaning None if a parameter was not reported for a particular independent axis value,
            # such as when a parameter is not reported for a particular timestamp or depth)
            ranges = {}
            for r in station_rows:
                axis_value = r[self.independent_axis_column_name]
                i = independent_axis_index[axis_value]
                for parameter_column_set in self.parameter_columns:
                    name = r[parameter_column_set["name_column"]]

                    # each list needs to be the same length for the ranges, so
                    # if a parameter name is None, we skip processing it for this row
                    # and it will already be set to None in the ranges for this independent axis value
                    if name is None or (
                        selected_properties is not None
                        and name not in selected_properties
                    ):
                        continue

                    if name not in ranges and name is not None:
                        ranges[name] = {
                            "type": "NdArray",
                            "dataType": parameter_column_set["data_type"],
                            "axisNames": [self.independent_axis],
                            "shape": [len(independent_axis_raw_values)],
                            "values": [None] * len(independent_axis_raw_values),
                        }

                    ranges[name]["values"][i] = r[parameter_column_set["value_column"]]

            # transform the raw independent axis values for the coverage output (e.g., ISO formatted timestamps)
            coverages.append(
                {
                    "type": "Coverage",
                    "id": str(thing_id),
                    "domain": {
                        "type": "Domain",
                        "domainType": self.domain_type,
                        "axes": {
                            "x": {"values": [lon]},
                            "y": {"values": [lat]},
                            self.independent_axis: {
                                "values": [
                                    self.independent_axis_transformer(raw_value)
                                    for raw_value in independent_axis_raw_values
                                ]
                            },
                        },
                        "referencing": self.referencing,
                    },
                    "ranges": ranges,
                }
            )

        return {
            "type": "CoverageCollection",
            "domainType": self.domain_type,
            "parameters": parameters,
            "coverages": coverages,
        }

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _parse_interval(datetime_):
        """Split an EDR datetime parameter into (start, end); '..' = open."""
        if "/" in datetime_:
            start, end = datetime_.split("/", 1)
            start = None if start in ("", "..") else start
            end = None if end in ("", "..") else end
            return start, end
        return datetime_, datetime_

    def _create_lexicon_categories(self, lexicon_category):
        """CoverageJSON categories for one lexicon category, read from the DB.

        The lexicon is the source of truth for a categorical parameter's
        allowed values, so the categories list every term in the category,
        not only the ones that occur in the response.
        """
        rows = self._fetch(
            "SELECT t.term, t.definition "
            "FROM lexicon_term t "
            "JOIN lexicon_term_category_association a ON a.term_id = t.id "
            "JOIN lexicon_category c ON c.id = a.category_id "
            "WHERE c.name = %s "
            "ORDER BY t.term",
            [lexicon_category],
        )
        return categories_from_lexicon(rows)

    def __repr__(self):
        return f"<StationEDRProvider> {self.table}"
