"""Isolation guarantees for the public (/ogcapi) and internal (/ogcapi-internal) mounts.

Both mounts are built from the same pygeoapi.starlette_app source, which
resolves PYGEOAPI_CONFIG at import time into a module-level ``api_`` that
every route handler reads out of module globals at request time. Loading the
second mount by reloading that module rebinds those globals in place, which
silently retargets the already-built first mount -- the public mount then
serves the unfiltered ogc_internal_* views, defeating the A1
``release_status = 'public'`` filter. These tests pin the isolation that
prevents that.

Importing this module builds the app (via the tests package), so both
runtime config files already exist on disk by the time a test runs.
"""

import os
import re
import sys

from core import pygeoapi

PUBLIC_MODULE = "pygeoapi.starlette_app__ocotillo_public"
INTERNAL_MODULE = "pygeoapi.starlette_app__ocotillo_internal"


def _mount_args():
    public_dir = pygeoapi._pygeoapi_dir()
    internal_dir = pygeoapi._pygeoapi_dir(
        "PYGEOAPI_INTERNAL_RUNTIME_DIR", "/tmp/pygeoapi-internal"
    )
    return (
        (
            "public",
            public_dir / "pygeoapi-config.yml",
            public_dir / "pygeoapi-openapi.yml",
        ),
        (
            "internal",
            internal_dir / "pygeoapi-config.yml",
            internal_dir / "pygeoapi-openapi.yml",
        ),
    )


def _load_both():
    # Internal last, matching create_api_app's order -- the order that used
    # to leave the public mount pointing at ogc_internal_* relations.
    public, internal = _mount_args()
    pygeoapi._load_pygeoapi_app(*public)
    pygeoapi._load_pygeoapi_app(*internal)
    return sys.modules[PUBLIC_MODULE], sys.modules[INTERNAL_MODULE]


def _provider_tables(api):
    return {
        name: resource["providers"][0].get("table")
        for name, resource in api.config["resources"].items()
        if resource.get("providers")
    }


def test_each_mount_gets_independent_module_globals():
    public_module, internal_module = _load_both()

    assert public_module is not internal_module
    # The aliasing that caused the leak: one shared dict, so one shared api_.
    assert public_module.__dict__ is not internal_module.__dict__
    assert public_module.api_ is not internal_module.api_


def test_public_mount_does_not_resolve_to_internal_relations():
    public_module, internal_module = _load_both()

    public_tables = _provider_tables(public_module.api_)
    assert public_tables, "public config exposed no provider-backed collections"
    leaked = {
        name: table
        for name, table in public_tables.items()
        if table and table.startswith("ogc_internal_")
    }
    assert not leaked, f"public mount resolves to internal relations: {leaked}"

    internal_tables = _provider_tables(internal_module.api_)
    assert internal_tables, "internal config exposed no provider-backed collections"
    misrouted = {
        name: table
        for name, table in internal_tables.items()
        if table and not table.startswith("ogc_internal_")
    }
    assert not misrouted, f"internal mount resolves to public relations: {misrouted}"


def test_each_mount_advertises_its_own_server_url():
    public_module, internal_module = _load_both()

    public_url = public_module.api_.config["server"]["url"]
    internal_url = internal_module.api_.config["server"]["url"]

    assert public_url != internal_url
    assert public_url == pygeoapi._server_url()
    assert internal_url == pygeoapi._internal_server_url()


def test_loading_a_mount_restores_config_env_vars():
    # Leaving the last-loaded mount's paths in the environment would decide
    # the config for anything that imports pygeoapi later in the process.
    before = {key: os.environ.get(key) for key in pygeoapi._PYGEOAPI_ENV_KEYS}

    _load_both()

    after = {key: os.environ.get(key) for key in pygeoapi._PYGEOAPI_ENV_KEYS}
    assert after == before


# Layers hidden from the public catalog but still served to staff GIS
# clients on /ogcapi-internal: locations duplicates the thing-type layers
# (BDMS-978), avg_tds_wells and latest_depth_to_water_wells are misleading
# or redundant (BDMS-977), other_things is internal vocabulary (BDMS-979).
INTERNAL_ONLY_COLLECTIONS = {
    "locations",
    "avg_tds_wells",
    "latest_depth_to_water_wells",
    "other_things",
}


def test_hidden_layers_are_internal_only():
    public_module, internal_module = _load_both()

    public_ids = set(public_module.api_.config["resources"])
    internal_ids = set(internal_module.api_.config["resources"])

    assert public_ids.isdisjoint(INTERNAL_ONLY_COLLECTIONS)
    assert INTERNAL_ONLY_COLLECTIONS.issubset(internal_ids)
    # The thing-type layers that stay public are on both mounts; the two
    # catalogs otherwise differ (the geothermal layers are public-only).
    assert {"water_wells", "springs"}.issubset(public_ids & internal_ids)


# Wording that says nothing to a consumer reading the catalog cold: internal
# data-model vocabulary, or a description that only restates the layer name.
PLACEHOLDER_TERMS = ("todo", "tbd", "xxx", "placeholder", "example.com", "lorem")


def test_every_collection_description_explains_the_layer():
    # A description has to tell a non-specialist how the layer was derived and
    # what it is for -- not repeat the title. Short entries are the failure
    # mode this guards: they are what the catalog shipped with before.
    for module in _load_both():
        for name, resource in module.api_.config["resources"].items():
            description = resource.get("description", "")
            lowered = description.lower()
            assert len(description) >= 200, f"{name} description is too thin"
            assert not any(
                term in lowered for term in PLACEHOLDER_TERMS
            ), f"{name} description contains placeholder wording"
            assert description.rstrip().endswith(
                "."
            ), f"{name} description is not a complete sentence"
            # YAML folds a line break into a space, so a hyphenated word split
            # across lines ("measuring-\npoint") reaches consumers as
            # "measuring- point". Wrap on whitespace only.
            assert not re.search(
                r"\w- \w", description
            ), f"{name} description has a hyphenated word split across lines"

            keywords = resource.get("keywords", [])
            assert len(keywords) >= 4, f"{name} has too few keywords"
            assert len(set(keywords)) == len(keywords), f"{name} repeats a keyword"
            for keyword in keywords:
                assert re.fullmatch(
                    r"[a-z0-9]+(?:-[a-z0-9]+)*", keyword
                ), f"{name} keyword {keyword!r} is not a lowercase hyphenated token"
