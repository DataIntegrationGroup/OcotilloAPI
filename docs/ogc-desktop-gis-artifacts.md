# Shareable QGIS and ArcGIS Pro artifacts

Downloadable files that get a desktop GIS user onto our OGC API - Features
collections without them configuring a connection by hand.

Landing page: **`/gis`**. Code:
[`services/gis_artifacts.py`](../services/gis_artifacts.py),
[`api/gis_artifacts.py`](../api/gis_artifacts.py), curated list in
[`core/gis-curated-layers.yml`](../core/gis-curated-layers.yml).

For connecting to the authenticated `/ogcapi-internal` mount, and for how API
keys are issued, see
[`internal-ogc-desktop-gis.md`](internal-ogc-desktop-gis.md).

## Two levels, per client

| | QGIS | ArcGIS Pro |
|---|---|---|
| Everything | `.xml` connections file — **generated** | `.ogc` connection file — **not generated**, see below |
| One layer | `.qlr` layer definition — **generated** | `.lyrx` layer file — **generated** |

```
GET /gis                                  landing page, links to everything
GET /gis/qgis/connections.xml             public mount
GET /gis/qgis/connections-internal.xml    public + internal (viewer role)
GET /gis/qgis/layers/{id}.qlr
GET /gis/arcgis/layers/{id}.lyrx
```

## Why these are generated rather than committed

Every artifact embeds an absolute service URL, and there are three environments
(production, staging, local) times two mounts. Committing static files means
six copies of each, and each goes stale the moment a collection is added —
production already advertises **30** collections against the 13 defined in
`core/pygeoapi.py`. Generating from the running app means the URL is always the
one the caller reached us on.

The artifacts take their base URL from `core.pygeoapi._server_url()`, the same
value pygeoapi stamps into its own `self` and `next` links. That is deliberate:
both clients follow those links to page through `items`, so an artifact
advertising a different host would work for one page and then walk off
somewhere else — the failure `PYGEOAPI_INTERNAL_SERVER_URL` was added to fix.

## The ArcGIS `.ogc` connection file is not generated

Pro writes a `.ogc` file into the project home folder when you add an OGC API
server connection, and that file is shareable — but **Esri does not document
its format**. It is not in the CIM spec, and the Pro help describes only where
the file lands, not what is in it. Rather than ship a guess that fails in the
one client we cannot test against, `/gis` tells the user the two-step click
path (*Insert > Connections > Server > New OGC API Server*, paste the URL) and
lets Pro write its own file, which they can then share.

To close this properly, someone with Pro should add the connection once and
send back the resulting `.ogc`; templating it after that is a small change to
`services/gis_artifacts.py`.

## EDR is deliberately absent from the curated layers

`waterlevels` and `water_chemistry` are served by the EDR provider only — they
publish no `/items` endpoint. **Neither QGIS nor ArcGIS Pro has an OGC API - EDR
client**, so a layer file pointing at either would not open. The curated
"water levels" layer is `latest_depth_to_water_wells`, which carries the same
measurement summarised per site, which is what a GIS user wants on a map.
`test_no_curated_layer_points_at_an_edr_collection` enforces this.

## The curated list is checked against *this branch*, not production

Production advertises 30 collections; this branch defines 13 in
`core/pygeoapi.py` plus 14 in the `core/pygeoapi-config.yml` template. A
curated layer written against a live deployment can therefore name a
collection that does not exist here, and the artifact 404s the moment a user
opens it. `test_every_curated_layer_names_a_collection_this_branch_serves`
reads both sources and fails on the mismatch. It caught exactly that during
development: the first draft of the "water levels" layer pointed at
`latest_depth_to_water_wells`, which only production serves. It now uses
`water_elevation_wells`.

## Aliases are intersected with the view's real columns

`_defaults` in `core/ogc-field-descriptions.yml` is a **shared pool, not a set
of universal columns** -- it carries well fields and geothermal fields side by
side, and `describe_fields` only ever applies the ones a given view actually
reflects. The generator must do the same intersection: unfiltered, a
nine-column collection ships aliases for 42 fields. QGIS silently drops the
ones it cannot match, but ArcGIS Pro takes `fieldDescriptions` at its word.

`collection_fields()` reflects `ogc_<collection>` from `information_schema`
and the routes pass the result through. It returns `None` when the view is
absent -- a branch whose migrations have not created it yet -- and the caller
then falls back to the full entry list rather than emitting a layer file with
no aliases at all.

## Field aliases and value maps are derived, not written twice

Aliases come from `core/ogc-field-descriptions.yml` through
`core.ogc_field_metadata.table_entries()` — the same file that feeds `/schema`
and `/queryables`. A renamed or re-titled field therefore cannot drift between
the API and the shipped layer files, and
`test_qlr_aliases_cover_every_documented_field` fails if one does.

Value maps are emitted **only where the display label differs from the stored
value**, which in practice means the categorised renderer's own labels. The
lexicon-backed columns (`thing_type`, `release_status`) already store terms
that read as prose, so mapping them to themselves would add kilobytes of
`name == value` noise per layer and give the user a dropdown that renames
nothing. `trend_category` is the real case: `increasing` means the water table
is *falling*.

## No artifact ever embeds a credential

QGIS's connection format has `username` and `password` attributes, and Esri's
`CIMInternetServerConnection` has a `user` field, so embedding a key is
possible in both formats. It is not done. Internal access uses per-user API
keys precisely so they can be revoked per user; a shared file carrying one
person's key defeats that. `connections-internal.xml` ships the internal URL
credential-free and the user attaches their own key in their own client.
`test_no_artifact_embeds_a_credential` guards this.

Note that Esri's own spec marks the CIM connection password *"not persisted in
documents"*, so `.lyrx` could not carry one even if we wanted it to.

## Verification

`tests/test_gis_artifacts.py` covers what can be checked without a GIS
installed: XML/JSON well-formedness, the datasource URI, tree-node and maplayer
agreement, renderer fields existing on the collection, alias coverage, the
EDR exclusion, credential absence, and QGIS/ArcGIS renderer agreement.

**That is not the same as the file opening.** The formats were established by
loading them into a real QGIS 4.0.1 (`QgsLayerDefinition.loadLayerDefinition`)
against the live production service, which confirmed for all six curated
layers: the layer loads valid on the `OAPIF` provider, serves live features
(2453 for the trend layer), and applies the renderer, every alias, the value
map and scale visibility.

Two findings from that exercise are worth keeping:

- **A malformed value map segfaults QGIS 4.0.1 rather than erroring.** Each
  entry must be its own `<Option type="Map">` wrapper whose single child is
  named for the display label and carries the stored value. Flattening that
  wrapper away crashes the process on load.
  `test_qlr_value_map_entries_are_nested_option_maps` pins the shape.
- The emitted `.qlr` is deliberately minimal — around 4–7 KB against the 27 KB
  QGIS itself exports. QGIS fills every omitted element with its own defaults.

QGIS is **not** a CI dependency, so re-run that check by hand when changing the
emitted XML. The procedure needs a PyQGIS bootstrap; on macOS:

```bash
Q=/Applications/QGIS-final-4_0_1.app/Contents
env PYTHONHOME="$Q/Frameworks" \
    PYTHONPATH="$Q/Resources/python3.11/site-packages:$Q/Resources/python" \
    PROJ_DATA="$Q/Resources/qgis/proj" QGIS_PREFIX="$Q/Resources" \
    QT_QPA_PLATFORM=offscreen "$Q/MacOS/python3.12" your_check.py
```

`QgsProviderRegistry.instance("$Q/PlugIns/qgis")` must be called before
`initQgis()` or no providers load and every layer comes back invalid. Reuse
`QgsProject.instance()` and `clear()` between files — constructing more than
one `QgsProject` segfaults.

The `.lyrx` files have **not** been opened in ArcGIS Pro; none is available to
this project. They are built to Esri's published CIM spec
(`CIMLayerDocument` → `CIMFeatureLayer` → `CIMOGCAPIServiceConnection`). Treat
the first open in Pro as the real test.

## Adding a curated layer

Add an entry to `core/gis-curated-layers.yml` with an `id`, a `collection` that
the Features mount serves, a `title`, and a `renderer` of type `single`,
`graduated` or `categorized`. The tests will fail if the renderer classifies on
a field with no entry in `core/ogc-field-descriptions.yml`, if the collection
is EDR-only, or if the id collides. Nothing else needs changing — the routes
and the landing page read the config.
