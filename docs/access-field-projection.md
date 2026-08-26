# Field projection: what an audience actually receives

Read this before editing `core/field-allowlists.yml`, adding a projectable
entity, or wiring a new consumer into published payloads.

The decision behind it is [ADR5](../ADR5.md), sections 3.5 and A.2.

## The rule

Fields are published by **allowlist, per audience, at one chokepoint**.

- Only fields named for an audience appear in that audience's payload.
  Omission produces silence, not leakage: a column added next year is
  invisible to everyone outside the Bureau until someone lists it.
- An audience with no entry receives an **empty record**, not the whole one.
- Protection includes **transformation**, not only removal. A public record can
  carry a coordinate rounded to protect the landowner while the precise value
  stays internal.
- The **never-public list wins** over every allowlist, and is applied twice:
  when the configuration loads, and again when a record is projected.

## Where the pieces are

| Piece | Path | Job |
| --- | --- | --- |
| Rules | `domain/field_projection.py` | Omit, transform, validate. Plain dicts; no database, no config parsing. |
| Configuration + chokepoint | `services/field_projection.py` | Parse and validate the YAML, build a record from a model row, project it. |
| Configuration | `core/field-allowlists.yml` | The allowlists and the never-public list. |
| Destination payloads | `services/visibility.py` (`published_things`) | Builds them through `project_entity`. |
| Public OGC collections | `core/feature_provider.py` | Reads `ogc_allowlist(table)` at provider construction. |

`api/access.py` never projects anything itself. That is the point: the
projection sits *below* the routes, so a new route or a new output format
cannot skip it by forgetting to call it.

## Adding a field for an audience

1. Add it to that audience's `fields` list in `core/field-allowlists.yml`,
   under `audiences.by_kind.<kind>` or `audiences.by_slug.<slug>`.
2. Run the tests. The configuration is validated on load, so a typo, a field
   the entity does not have, or a field on the never-public list fails
   immediately rather than quietly withholding or exposing data.

A `by_slug` entry **replaces** the rules for that destination's kind rather
than extending them, so what one partner receives is readable in one place.

## Adding a transform

Transforms live in `TRANSFORMS` in `domain/field_projection.py` and are named
in the YAML as `field: {transform: argument}`. Only `round` exists today:

```yaml
transforms:
  latitude:
    round: 2
```

Two decimal places is roughly a kilometre; four is roughly ten metres. A
transform on a field that is not in the same allowlist raises at load, because
it would never run.

## The never-public list

`never_public` in the YAML is the list no configuration can override.
Engineering guarantees that whatever is listed is enforced everywhere.
Engineering **cannot decide what belongs on it** — that needs a named data
owner, and ADR5 records that nobody has been named yet.

What that means in practice:

- **Adding** a field to `never_public` is safe at any time and needs no
  ceremony.
- **Removing** one is not an engineering call. If a removal seems necessary,
  the question goes to the data owner, not into a pull request.

Currently listed: provenance columns (`created_by_*`, `updated_by_*`), legacy
AMPAPI primary keys, and the free-text location and coordinate note columns —
the permissions interview was explicit that gate codes, lock combinations and
candid landowner notes must never leave the Bureau, and that is the text those
columns have collected.

## The OGC collections

The public `/ogcapi` mount serves 27 collections from three places: fifteen
declared in `core/pygeoapi-config.yml`, ten built from `THING_COLLECTIONS` in
`core/pygeoapi.py`, and two EDR collections wired there too. Missing that third
source is how eleven collections published `nma_pk_welldata` unnoticed.

`DescribedPostgreSQLProvider` looks each table up in the `ogc:` block of
`core/field-allowlists.yml` and hands the result to pygeoapi as the provider's
`properties`. That is what `_select_properties` builds the SELECT from, so an
unlisted column is never read out of Postgres at all: it cannot appear in a
feature, in `/schema`, or in `/queryables`, and a filter cannot probe for it.
`get_fields` is narrowed to match, since the reflection sees the whole view.

**Adding a collection** means adding its table to `ogc.collections`. Without an
entry it publishes *no* properties — default deny, logged as a warning — and
`tests/test_ogc_projection.py` fails, so a missing entry shows up in CI rather
than in production.

**The internal mount is not projected.** `ogc_internal_*` tables return `None`
from `ogc_allowlist` and pass through whole. It serves authenticated Bureau
staff, and per-role internal field rules are the part of ADR5 3.5 that is not
built.

The lists were generated from what each view published on 2026-08-24 minus the
never-public fields, so no consumer lost a field it was using. That makes the
file a record of what is public rather than an aspiration — narrowing it is
the next deliberate step, and it should happen.

## What this does *not* cover

The desktop-GIS layer files in `core/gis-curated-layers.yml` are not a separate
publication path — they point clients at the OGC collections above and so
inherit the projection.

Only `thing` and `location` are projectable entities for destination payloads. Adding another means
adding it to `ENTITY_MODELS` (and `DERIVED_FIELDS` if the payload carries
values that are not columns, the way `latitude` and `longitude` stand in for
the PostGIS `point`).

Field rules are per *audience* today. ADR5 also asks for field rules between
internal roles — contact information being AMP-only is one — and that case is
not implemented.
