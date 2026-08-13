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
CoverageJSON directly from the publication-filtered ``ogc_waterlevels`` and
``ogc_water_chemistry`` views.

Each backing view is a flat table of readings with the columns::

    id, thing_id, station_name, longitude, latitude, datetime,
    value, unit, parameter_name, release_status
    (+ deployment_id on ogc_waterlevels)

The provider groups readings by station (``thing_id``) into a CoverageJSON
``PointSeries`` coverage, one parameter per ``parameter_name``. Transducer
deployments (``deployment_id``) are exposed as EDR instances of the
``waterlevels`` collection.
"""

import logging
import os
import re

import psycopg2
from psycopg2.extras import RealDictCursor

from pygeoapi.provider.base import (
    ProviderConnectionError,
    ProviderNoDataError,
)
from pygeoapi.provider.base_edr import BaseEDRProvider

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


class WaterEDRProvider(BaseEDRProvider):
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
        self.table = provider_def.get("table")
        self.id_field = provider_def.get("id_field", "id")
        self.time_field = "datetime"
        # Only the waterlevels collection exposes transducer instances.
        self.instance_field = provider_def.get("instance_field")

        self._fields = {}
        self.get_fields()

        # Station metadata carried by some backing views but not others: the
        # chemistry views (d9e0f1a2b3c4) span wells and springs and expose
        # thing_type so a consumer can tell them apart. Detected rather than
        # assumed, so a view without the column keeps working unchanged.
        self._has_thing_type = self._has_column("thing_type")

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
        """Return the parameter-name fields present in the backing view."""
        if self._fields:
            return self._fields
        try:
            rows = self._fetch(
                f"SELECT DISTINCT parameter_name, unit "  # noqa: S608 (trusted table)
                f"FROM {self.table} ORDER BY parameter_name"
            )
        except ProviderConnectionError:
            # View may not exist yet (e.g. OpenAPI generation before migrate).
            return {}
        for row in rows:
            self._fields[row["parameter_name"]] = {
                "type": "number",
                "title": row["parameter_name"],
                "x-ogc-unit": row["unit"],
            }
        return self._fields

    @property
    def fields(self):
        return self.get_fields()

    # ----------------------------------------------------------- instances
    def get_instances(self):
        """List transducer-deployment instance identifiers."""
        if not self.instance_field:
            return []
        rows = self._fetch(
            f"SELECT DISTINCT {self.instance_field} AS iid "  # noqa: S608
            f"FROM {self.table} WHERE {self.instance_field} IS NOT NULL "
            f"ORDER BY {self.instance_field}"
        )
        return [str(row["iid"]) for row in rows]

    def get_instance(self, instance):
        """Validate an instance identifier."""
        return instance in set(self.get_instances())

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
            return self._coverage_collection(rows)

        # location listing: one feature per station with data
        clauses, params = self._filters(
            datetime_=datetime_,
            select_properties=select_properties,
            instance=instance,
            bbox=bbox,
        )
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        columns = "thing_id, station_name, longitude, latitude"
        if self._has_thing_type:
            columns += ", thing_type"
        rows = self._fetch(
            f"SELECT DISTINCT {columns} "  # noqa: S608 (trusted table/columns)
            f"FROM {self.table}{where} ORDER BY thing_id",
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
        properties = {"name": row["station_name"]}
        if self._has_thing_type:
            properties["thing_type"] = row["thing_type"]
        return properties

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
        return self._coverage_collection(rows)

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
        return self._coverage_collection(rows)

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
        return self._coverage_collection(rows)

    # --------------------------------------------------------- read/filter
    def _filters(
        self, datetime_=None, select_properties=None, instance=None, bbox=None, wkt=None
    ):
        clauses = []
        params = []
        if datetime_:
            start, end = self._parse_interval(datetime_)
            if start is not None:
                clauses.append("datetime >= %s")
                params.append(start)
            if end is not None:
                clauses.append("datetime <= %s")
                params.append(end)
        if select_properties:
            clauses.append("parameter_name = ANY(%s)")
            params.append(list(select_properties))
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
        return self._fetch(
            f"SELECT thing_id, station_name, longitude, latitude, "  # noqa: S608
            f"datetime, value, unit, parameter_name "
            f"FROM {self.table}{where} "
            f"ORDER BY thing_id, parameter_name, datetime",
            params,
        )

    # ------------------------------------------------------- coveragejson
    def _coverage_collection(self, rows):
        if not rows:
            raise ProviderNoDataError("No data found")

        parameters = {}
        # group rows by (thing_id) -> per station coverage, and by parameter
        stations = {}
        for row in rows:
            stations.setdefault(row["thing_id"], []).append(row)
            name = row["parameter_name"]
            if name not in parameters:
                parameters[name] = {
                    "type": "Parameter",
                    "description": {"en": name},
                    "observedProperty": {"id": name, "label": {"en": name}},
                    "unit": {"symbol": row["unit"], "label": {"en": row["unit"]}},
                }

        coverages = []
        for thing_id, srows in stations.items():
            lon = srows[0]["longitude"]
            lat = srows[0]["latitude"]
            by_param = {}
            for r in srows:
                by_param.setdefault(r["parameter_name"], []).append(r)

            # union of timestamps across params for this station
            times = sorted({r["datetime"] for r in srows})
            t_index = {t: i for i, t in enumerate(times)}
            ranges = {}
            for name, prows in by_param.items():
                values = [None] * len(times)
                for r in prows:
                    values[t_index[r["datetime"]]] = r["value"]
                ranges[name] = {
                    "type": "NdArray",
                    "dataType": "float",
                    "axisNames": ["t"],
                    "shape": [len(times)],
                    "values": values,
                }
            coverages.append(
                {
                    "type": "Coverage",
                    "id": str(thing_id),
                    "domain": {
                        "type": "Domain",
                        "domainType": "PointSeries",
                        "axes": {
                            "x": {"values": [lon]},
                            "y": {"values": [lat]},
                            "t": {"values": [t.isoformat() for t in times]},
                        },
                        "referencing": [GEOGRAPHIC_CRS, TEMPORAL_RS],
                    },
                    "ranges": ranges,
                }
            )

        return {
            "type": "CoverageCollection",
            "domainType": "PointSeries",
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

    def __repr__(self):
        return f"<WaterEDRProvider> {self.table}"
