# OGC field descriptions

Collection-level prose — `title`, `description`, `keywords` — lives in
`core/pygeoapi.py` (`THING_COLLECTIONS`, `EDR_COLLECTIONS`) and the two
pygeoapi config templates. This document covers the level below it: what an
individual **column** means, and what unit it is in.

Published through the standard endpoints:

| Endpoint | Standard | Carries |
| --- | --- | --- |
| `GET /collections/{id}/schema` | OGC API - Features Part 5 (draft), Common Part 3 | `title`, `description`, `x-ogc-unit`, `x-ogc-unitLang`, plus pygeoapi's own `x-ogc-role` |
| `GET /collections/{id}/queryables` | OGC API - Features Part 3 | the same `title` and `description` |

Both mounts serve both endpoints. EDR collections additionally carry the
documentation in their CoverageJSON `parameters` block
(`observedProperty.label` and `description`).

## Where the copy lives

`core/ogc-field-descriptions.yml`, keyed by **backing relation** with the
`ogc_` / `ogc_internal_` prefix stripped:

```yaml
_defaults:
  id:
    title: Feature ID
    description: >-
      Stable identifier for this feature within the collection.

water_well_summary:
  water_level_trend_ft_per_year:
    title: Water-level trend
    description: >-
      Slope of a straight line fitted through the well's depth-to-water
      measurements over time, in feet per year. Positive means the water
      table is falling.
    x-ogc-unit: https://qudt.org/vocab/unit/FT-PER-YR
    x-ogc-unitLang: QUDT
```

Keying by relation rather than collection id means the public and internal
mounts share one entry per view, and the provider looks itself up from
`self.table` with no extra plumbing. `_defaults` applies everywhere and a
per-table entry wins over it — which matters for a name like `description`,
whose meaning differs between `locations` and `project_areas`.

Allowed keys: `title`, `description`, `x-ogc-unit`, `x-ogc-unitLang`,
`x-ogc-propertySeq`. Anything else fails validation at load. Types and formats
come from the provider's reflection and must never be set here.

### Adding a field

1. Add the entry under the table's block, or under `_defaults` if the column
   means the same thing in every view that has it.
2. Say what the value means and what its datum or convention is — not how the
   view is built. That belongs in the collection description.
3. Run `uv run pytest tests/test_ogc_field_descriptions.py`.

The 190 chemistry analyte columns are generated:

```bash
uv run python -m cli.generate_chemistry_field_descriptions
```

Review the output and paste it into the YAML. The generator reads the analyte
lists out of the view migration — `core/parameter.json` holds only two field
parameters, so the lexicon cannot supply this. A hand-written entry in the YAML
wins over the generated one.

### Why not `COMMENT ON COLUMN`

It would put the prose next to the data, but every wording fix would need an
Alembic revision and a materialized-view rebuild, and pygeoapi's reflection does
not read column comments, so a catalog query would be needed anyway. This was
considered and rejected; please don't relitigate it without a new argument.

## How it reaches the client

`core/feature_provider.py` — `DescribedPostgreSQLProvider` — annotates the
reflected fields. Every feature collection in both config templates and in
`_thing_collections_block` names it as its provider.

`core/pygeoapi_patches.py` wraps `get_collection_queryables`.

`core/edr_provider.py` routes its parameter fields through the same YAML.

## What this depends on inside pygeoapi (0.24.0)

These are unpinned behaviours of a pinned version. **Re-check every one of them
when bumping pygeoapi**; `tests/test_ogc_field_descriptions.py` guards the first.

1. **`pygeoapi/api/__init__.py::get_collection_schema`** (~line 1082) assigns the
   provider's field entry into the response wholesale
   (`schema['properties'][k] = v`), so anything the provider attaches passes
   through. This is why `/schema` needs no patch.
2. It then **mutates that same dict in place** — `v.pop('format', None)`, and
   assigns `x-ogc-role`. `describe_fields()` therefore returns fresh dicts;
   handing out references into the cached YAML would let one request's
   mutations leak into the next.
3. **`pygeoapi/api/itemtypes.py::get_collection_queryables`** (~line 198) builds
   a fresh dict per property and hardcodes `'title': k`. Hence the patch.
4. **`pygeoapi/provider/base.py::BaseProvider.fields`** (~line 107) returns
   `self._fields` directly and **never calls `get_fields()`**, while
   `GenericSQLProvider.__init__` (~line 143) calls `get_fields()` once at
   construction. A `get_fields()` override that only returns an annotated copy
   is silently discarded — it must write back into `self._fields`.
5. **`pygeoapi/starlette_app.py`** imports `pygeoapi.api.itemtypes` as a module
   and resolves handlers off it per request, so rebinding the module attribute
   reaches both mounts even though each gets its own `starlette_app` module
   object.

## Deliberate gaps

- **`geometry`** carries no title. pygeoapi injects it after the provider's
  fields with only a `format` and `x-ogc-role`, so it is excluded from the
  "every property is documented" assertions.
- **`ogc_water_chemistry` parameters** are the analyte text exactly as the
  laboratory recorded it — open-ended, alias-ridden, and only knowable from the
  data. Undocumented analytes get a generated title from the parameter name.
- **A missing entry never fails a request.** It yields a generated title
  (`depth_to_water_bgs` → `Depth To Water Bgs`) and a logged warning. The drift
  guard in the tests is what fails the build.
