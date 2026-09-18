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
"""Feature provider that projects the published columns and documents them.

Two jobs, both on the way out of pygeoapi's PostgreSQL provider.

**Projection (ADR5, A.2).** Every public collection publishes the columns
named for it in ``core/field-allowlists.yml`` and no others. The allowlist is
handed to pygeoapi as the provider's ``properties``, which is what
``_select_properties`` builds the SELECT from, so an unlisted column is never
read out of Postgres -- it cannot appear in a feature, in ``/schema``, or in
``/queryables``, and a filter cannot probe it. ``get_fields`` is narrowed to
match, because the reflection sees the whole view.

A public collection with no allowlist entry publishes no properties. That is
default deny, and ``tests/test_ogc_projection.py`` fails when an entry is
missing so it surfaces in CI rather than in production. The internal mount
(``ogc_internal_*``) is not projected: it serves authenticated Bureau staff,
and per-role internal field rules are the part of ADR5 3.5 that is not built.

**Documentation.** pygeoapi reflects a table and reports each column's JSON
Schema type and format. It does not read column comments, and there is no hook
for documentation, so ``/collections/{id}/schema`` publishes bare column names.
This subclass annotates the reflected fields from
``core/ogc-field-descriptions.yml``.

Read docs/ogc-field-descriptions.md and docs/access-field-projection.md before
changing this.
"""

import logging

from pygeoapi.provider.sql import PostgreSQLProvider

from core.ogc_field_metadata import describe_fields
from services.field_projection import ogc_allowlist

LOGGER = logging.getLogger(__name__)


class DescribedPostgreSQLProvider(PostgreSQLProvider):
    """PostgreSQLProvider that projects published columns and annotates them."""

    def __init__(self, provider_def):
        table = provider_def.get("table")
        self._allowlist = ogc_allowlist(table)

        if self._allowlist is not None:
            # pygeoapi reads `properties` in _select_properties and in get(),
            # so setting it here is what actually keeps the column out of the
            # query rather than out of the response only.
            provider_def = dict(provider_def, properties=sorted(self._allowlist))
            if not self._allowlist:
                LOGGER.warning(
                    "%s has no entry in core/field-allowlists.yml, so it "
                    "publishes no properties. Add one deliberately.",
                    table,
                )

        super().__init__(provider_def)

    def _published(self, fields: dict) -> dict:
        """Drop reflected fields the allowlist does not name."""
        if self._allowlist is None:
            return fields
        return {
            name: field for name, field in fields.items() if name in self._allowlist
        }

    def get_fields(self):
        """Reflect the table, then annotate the result.

        The write back into ``self._fields`` is the point of this method, not
        an optimisation. ``BaseProvider.fields`` -- which is what
        ``get_collection_schema`` and ``get_collection_queryables`` actually
        read -- returns ``self._fields`` directly and never calls
        ``get_fields()``. A subclass that only returned an annotated copy
        would be silently ignored, since ``GenericSQLProvider.__init__``
        populates ``_fields`` with the raw reflection at construction.
        """
        fields = super().get_fields()
        if fields and not getattr(self, "_fields_described", False):
            # Narrow before describing: a column nobody publishes has no
            # business in /schema or /queryables, described or not.
            self._fields = describe_fields(self.table, self._published(fields))
            # super().get_fields() short-circuits on a populated _fields, so
            # without this flag a later call would re-describe the annotated
            # dict. Harmless today (describe_fields is idempotent) but it
            # would quietly depend on that staying true.
            self._fields_described = True
        return self._fields
