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
"""Runtime patches over pygeoapi.

Only one, and only because pygeoapi leaves no hook for it.
``get_collection_schema`` copies a provider's field entries into its response
wholesale, so the documentation ``DescribedPostgreSQLProvider`` attaches
reaches the client untouched. ``get_collection_queryables`` instead builds a
fresh dict per property and hardcodes ``'title': k`` -- the raw column name --
dropping every description on the floor.

Rather than fork the 130-line handler, this wraps it and merges the
provider's own ``title``/``description`` into the JSON it returned. The cost
is a JSON round trip on a low-traffic endpoint; the benefit is that the rest
of pygeoapi's logic (property filtering, domains, enums, roles) stays theirs.

Read docs/ogc-field-descriptions.md before changing this, and re-check it on
any pygeoapi upgrade.
"""

import json
import logging

LOGGER = logging.getLogger(__name__)

# Keys taken from the provider's field entry when the handler dropped them.
DOCUMENTATION_KEYS = ("title", "description", "x-ogc-unit", "x-ogc-unitLang")

_QUERYABLES_PATCHED = False


def _documented_fields(api, dataset):
    """The provider's annotated fields for ``dataset``, or ``{}``.

    Never raises: queryables must keep working for a collection whose backing
    view is missing, exactly as it did before this patch.
    """
    try:
        from pygeoapi.plugin import load_plugin
        from pygeoapi.provider import get_provider_by_type

        providers = api.config["resources"][dataset]["providers"]
        # Builds a second provider for the request: the handler's own instance
        # is local to it. That costs one table reflection on an endpoint that
        # is queried rarely and cached downstream.
        provider = load_plugin("provider", get_provider_by_type(providers, "feature"))
        return provider.fields or {}
    except Exception as err:  # noqa: BLE001 - documentation is never fatal
        LOGGER.debug("No documented fields available for %s: %s", dataset, err)
        return {}


def _merge_documentation(payload: str, fields: dict) -> str:
    document = json.loads(payload)
    properties = document.get("properties")
    if not isinstance(properties, dict):
        return payload

    for name, prop in properties.items():
        field = fields.get(name)
        if not isinstance(field, dict):
            continue
        for key in DOCUMENTATION_KEYS:
            value = field.get(key)
            if value is not None:
                prop[key] = value

    return json.dumps(document, indent=4)


def apply_queryables_patch() -> None:
    """Make /collections/{id}/queryables carry the provider's field prose.

    Idempotent, and deliberately not config-dependent: pygeoapi.api.itemtypes
    is a single module object shared by both mounts, and starlette_app
    resolves the handler off it per request, so patching once before either
    mount is built covers both.
    """
    global _QUERYABLES_PATCHED
    if _QUERYABLES_PATCHED:
        return

    import pygeoapi.api.itemtypes as itemtypes

    original = itemtypes.get_collection_queryables

    def get_collection_queryables(api, request, dataset=None):
        headers, status, content = original(api, request, dataset)

        # Leave HTML rendering, errors, and anything unparseable alone.
        if status != 200 or not isinstance(content, str):
            return headers, status, content
        if not headers.get("Content-Type", "").startswith("application/schema+json"):
            return headers, status, content

        fields = _documented_fields(api, dataset)
        if not fields:
            return headers, status, content

        try:
            return headers, status, _merge_documentation(content, fields)
        except (ValueError, TypeError) as err:
            LOGGER.warning("Could not annotate queryables for %s: %s", dataset, err)
            return headers, status, content

    get_collection_queryables.__wrapped__ = original
    itemtypes.get_collection_queryables = get_collection_queryables
    _QUERYABLES_PATCHED = True
    LOGGER.debug("Patched pygeoapi get_collection_queryables for field descriptions.")
