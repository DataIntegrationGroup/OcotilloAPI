# Water well field operations layer — design

Status: **implemented** on `feat/amp-field-operations-ogc-layer`, then
consolidated with an independently-drafted layer
(`kas-water-well-operations-ogc-layer-bdms-1202`) on
`kas-water-well-field-operations-ogc-layer-bdms-1202` after a side-by-side
column comparison. Migration `e1f2a3b4c5d6`; column-by-column source table in
`docs/water-well-field-operations-columns.md`.

Two questions this document opened were settled before implementation: "AMP" is
a label for the crews' view of the register, not a subset of it, so the layer
covers every water well; and the contact detail in §4 is published in full
(option A).

The consolidation dropped several columns this document originally specified
(`nma_pk_welldata`, `county`, `state`, `quad_name`, `elevation_method`,
`nma_formation_zone`, `measuring_point_start_date`, every `*_since`/`*_reason`
status/frequency column, and `access_status` itself -- open question 2 below,
resolved), renamed
several to match the naming already established on the public thing-type views
(`station_type`, `well_purpose`, `well_casing_material`, `mp_height`/
`mp_description`, `date_last_visited`), added `formation_completion_description`
and `aquifer_system_name`, broadened the equipment columns from logger-only to
every currently-installed sensor, and added a column per remaining
`notes.note_type` value. The rest of this document describes the layer as
originally designed; §6 and §11 call out where the shipped column set now
differs.

## 0. Why the name does not say AMP

The layer was requested as `amp_field_well_operations` and renamed before it
merged, per the pre-merge check in `docs/ogc_conventions.md`. Three rules
pushed the same way:

- `amp` is an unexpanded abbreviation, which the do/don't rules forbid
  outright ("Spell abbreviations out in full ... If the accurate name is long,
  that's fine"). Its expansion is recorded nowhere in this codebase, so a
  consumer could not resolve it even in principle.
- AMP is a label for who uses the layer, not a filter on what is in it — the
  row set is every water well, with no group predicate. A name carrying `amp`
  would claim a scope the data does not have, which is its own Don't.
- Group B analytic layers prefer a `water_well_` prefix over a `_wells`
  suffix, and this is one.

The AMP crews remain the layer's audience; that belongs in the description,
which says so, rather than in an identifier that is a long-term commitment.

A new OGC API - Features collection, `water_well_field_operations`, published on
`/ogcapi-internal` only. One feature per water well, carrying everything a
field crew needs to plan and execute a visit: where the well is, who owns it
and how to reach them, what the crew is allowed to do there, what is installed
in it, and when it was last measured.

Every other well layer in the catalogue answers a scientific question — what is
the water level, what is the chemistry, what is the trend. This one answers an
operational one: **can we go to this well, what are we allowed to do when we
get there, and is it overdue?**

## 1. Why a new layer rather than a column pass on an existing one

`water_wells` is the construction register and is public. `water_well_summary`
and `actively_monitored_wells` summarise the measurement record and are public.
The operational fields — landowner phone numbers, access notes, sampling
permissions — cannot go on any of those, because those layers are published
anonymously. The split is a publication boundary, not a modelling preference.

## 2. Scope

**In:** water wells. `thing_type = 'water well'`, the same predicate every
other well layer in this catalogue uses. Springs, streams, and met stations are
out even though crews visit them — this is the wells layer, per the request.

`thing_type` in the lexicon also carries `observation well`, `piezometer`,
`monitoring well`, `production well`, `injection well`, `exploration well`,
`test well`, `abandoned well`, `dry hole`, `artesian well`, and `dug well`.
None of them are included. That matches `ogc_water_wells`,
`ogc_water_well_summary`, and `ogc_well_water_column`, so the layers cannot
disagree about which rows are "wells" — see §11, open question 1.

**Row set:** every water well with a current location, including wells with no
measurement record at all. A well nobody has ever measured is exactly the well
a field crew needs to find, so this layer must not inherit
`water_well_summary`'s `total_water_levels > 0` restriction.

**Release status:** unfiltered. The internal mount is unfiltered by design and
this layer has no public twin, so there is no `release_status = 'public'`
predicate anywhere in it. `release_status` is published as a column so a
consumer can see what they are looking at.

## 3. Placement: internal-only, no public counterpart

Every other `ogc_internal_*` relation is the unfiltered twin of a public
`ogc_*` one. This layer deliberately breaks that: `ogc_internal_water_well_field_operations`
exists and `ogc_water_well_field_operations` does not, and must never be created.

This does not disturb the existing parity guard.
`tests/test_migration_view_parity.py::test_internal_migration_mirrors_every_public_relation`
reads two named migration files (`f4a5b6c7d8e9` and `2d3c3a268652`) and asserts
that internal file mirrors that public file's 24 relations. A relation created
by a *new* migration is outside what that test reads, so the count assertion
stays at 24 and stays true.

Precedent for an internal-only collection: `locations`, `avg_tds_wells`,
`latest_depth_to_water_wells` (static entries in the internal config template
only) and `other_things` (`internal_only: True` in `THING_COLLECTIONS`).

Because this layer is not a thing-type register, it is wired the same way
`locations` is: a static block in `core/pygeoapi-config-internal.yml`, not an
entry in `THING_COLLECTIONS`.

## 4. The PII decision — read this before implementing

This layer publishes landowner and operator contact details: name,
organization, role, phone number, email address. That is what "contact info"
means for a field crew, and it is why the layer is internal-only.

The consequence is not confined to this layer. `/ogcapi-internal` is reachable
two ways on this branch (`core/internal_ogc_auth.py`): an Authentik JWT
carrying `OGC.Internal`, or a static API key from `INTERNAL_OGC_API_KEYS`.
**Shipping this layer means every one of those credentials becomes a credential
that dispenses landowner personal information**, and any credential path added
later -- the user-issued keys on `feat/api-key-management` among them --
inherits the same reach. The static desktop-GIS keys in particular are shared
secrets that can only be revoked by redeploy.

pygeoapi has no per-field authorization — a column is either in the view or it
is not — so this is all-or-nothing per layer. Three options:

| Option | What crews get | Cost |
| --- | --- | --- |
| **A. Full contact detail** (recommended) | Name, organization, role, phone, email | Every internal credential now dispenses PII |
| B. Presence only | `contact_count`, `primary_contact_organization`, `primary_contact_role` — no name, phone, or email | Crews must look the owner up in the UI before every visit; layer half-fails its purpose |
| C. Second layer | `water_well_field_operations` without PII, `water_well_field_contacts` with it | Two layers, two configs, two sets of field docs, same credentials still reach both — the split buys nothing without per-layer auth |

**Decision: A.** The request was explicit, the mount is authenticated, and B
makes the layer not worth building. Shipped with:

- A notice at the top of `docs/internal-ogc-desktop-gis.md` stating that an
  internal credential now conveys landowner PII, so key issuance is a decision
  made with that in mind. **`docs/api-key-management.md` still needs the same
  notice** — that file lives on `feat/api-key-management` and does not exist on
  this branch, so it could not be edited here.
- The collection `description` says so too, so it is visible in the catalogue
  itself.
- The layer does not filter contacts on `release_status`. `Contact` carries one,
  but the internal mount is unfiltered by design and this layer has no public
  twin to keep in step with.

## 5. Relations: one matview, one view

Two relations, not one, because the columns divide cleanly by cost *and* by how
badly staleness hurts:

```
ogc_internal_water_well_field_operations_stats   MATERIALIZED VIEW, keyed thing_id
    counts, first/last dates, aggregates over observation and
    transducer_observation. Expensive. Refreshed nightly.

ogc_internal_water_well_field_operations         VIEW  <- pygeoapi points here
    live join of thing, location, status_history, permission_history,
    deployment, sensor, contact, notes
    LEFT JOIN the stats matview
```

Reasons for the split:

1. **Staleness is dangerous on exactly the cheap columns.** "May we sample this
   well" and "is access currently granted" must not be up to 24 hours old. A
   revoked permission that still reads `true` until the next nightly refresh
   sends a crew onto land they are no longer welcome on. `permission_history`
   and `status_history` are small and indexed by `(target_id, target_table)`;
   reading them live costs nothing.
2. **`CURRENT_DATE` freezes in a matview.** The current-record rule in §7 is
   date-relative. Evaluated inside a materialized view it would be pinned to
   the refresh time, and a permission that expired this morning would still
   read as current tonight. It has to be in the plain view.
3. **The expensive columns don't need to be fresh.** A reading count and a
   last-measured date are fine at 24 hours old.

Plain views already back the eleven thing-type collections, so pygeoapi serving
a non-materialized view is established. Filtering and bbox pushdown resolve
against the base tables' indexes.

`_stats` carries a unique index on `thing_id` so it can be refreshed
`CONCURRENTLY` (`oco refresh-matview --concurrently`). The nightly pg_cron job
discovers every matview in the `public` schema by name, so it is picked up with
no schedule change. Add it to `MATERIALIZED_VIEWS` in
`services/materialized_views.py` for the CLI path.

## 6. Columns

`id` is `thing.id` and is unique — pygeoapi's `id_field: id` requires exactly
one row per id for `/items/{id}`. Every one-to-many is therefore aggregated.

Multi-valued columns are emitted as **`text`, comma-space joined**, not as
Postgres arrays. `ogc_actively_monitored_wells` uses `text[]` and that is fine
for a layer read in a browser, but this one exists to be pulled into ArcGIS Pro
and QGIS and exported to a File Geodatabase or GeoPackage for offline field
use, and neither format has a list type. A joined string survives the round
trip; an array does not.

### Identity and location

| Column | Source |
| --- | --- |
| `id` | `thing.id` |
| `name` | `thing.name` |
| `station_type` | `'water well'::text`. Named `station_type` rather than `thing_type` to match the naming already established on the public thing-type views (consolidation, see the note at the top of this document) |
| `release_status` | `thing.release_status` |
| `alternate_ids` | `thing_id_link`, joined as `organization:alternate_id` pairs |
| `latitude`, `longitude` | `ST_Y`/`ST_X` of the same point, decimal degrees on WGS 84 -- a plain number survives a CSV export, which drops the geometry, and a crew can read it into a handheld GPS |
| `elevation` | `location.elevation` |
| `point` | `location.point`, most recent association (the shared `LATEST_LOCATION_CTE`) |

`nma_pk_welldata`, `county`, `state`, `quad_name`, `nma_formation_zone`, and
`elevation_method` (and its `data_provenance` lookup) were dropped in the
consolidation. None of the four history-table current-record joins below
needed them, and none of the columns this layer is actually for -- status,
permission, equipment, contacts -- depend on them either.

### Well construction

`well_depth`, `hole_depth`, `well_casing_diameter`, `well_casing_depth`,
`well_completion_date`, `well_driller_name`, `well_construction_method`,
`well_pump_type`, `well_pump_depth`, `formation_completion_code` — all straight
from `thing`, same columns and same names as the thing-view template, so a
crew reading both layers sees one vocabulary.

Plus, aggregated:

| Column | Source |
| --- | --- |
| `formation_completion_description` | `lexicon_term.definition` where `term = thing.formation_completion_code` -- the code alone is not self-explanatory |
| `well_purpose` | `well_purpose.purpose`, joined |
| `well_casing_material` | `well_casing_material.material`, joined |
| `aquifer_system_name` | `aquifer_system.name` via `thing_aquifer_association`, joined |
| `screen_count` | `count(well_screen)` |
| `screen_depth_top`, `screen_depth_bottom`, `screen_description` | every screened interval, ft below ground surface, semicolon-joined, ordered shallowest first |

The original design collapsed `well_screen` to `screen_count` plus an overall
`min`/`max` depth range, avoiding the per-interval alignment problem below at
the cost of the actual intervals: for a well with two screens, a range says
there's screened section somewhere between the shallowest top and the
deepest bottom, not where the gap between them is, or what each one is made
of. The consolidation restored full per-interval detail instead, on the
premise that a driller doing rehab work needs the real intervals, not a
range. All three columns are ordered by `screen_depth_top` (nulls last) and
each is wrapped in `COALESCE(..., '')` before `string_agg`, for the same
reason as the equipment columns below: `screen_depth_top`,
`screen_depth_bottom`, and `screen_description` are all nullable
independently of each other, and plain `string_agg` would drop a null and
misalign the other two columns' positions.

`formation_completion_description` and `aquifer_system_name` are both from the
consolidation. Neither is date-windowed like the four history tables below --
`thing.formation_completion_code` is a plain column and
`thing_aquifer_association` carries no `start_date`/`end_date` at all.

### Measuring point (current record only)

| Column | Source |
| --- | --- |
| `mp_height` | `measuring_point_history.measuring_point_height`, ft above ground surface |
| `mp_description` | e.g. "North side of casing, top of PVC" |

The description is the single most useful string on the layer for a crew
standing at a wellhead. Current record per §7. `measuring_point_start_date`
(when the current configuration took effect) was dropped in the consolidation,
along with the equivalent `_since` column for every status type below.

### Status (current record per status type)

`status_history.status_type` has five values in the lexicon. `Access Status`
is not published -- see open question 2, resolved in the consolidation -- so
four of the five are:

| Column | `status_type` | Values |
| --- | --- | --- |
| `well_status` | Well Status | Abandoned; Active, pumping well; Destroyed, exists but not usable; Inactive, exists but not used |
| `monitoring_status` | Monitoring Status | Currently monitored; Not currently monitored |
| `open_status` | Open Status | Open; Open (unequipped); Closed |
| `datalogger_suitability_status` | Datalogger Suitability Status | Datalogger can be installed; Datalogger cannot be installed |

The original design also published a `<type>_since` column per status type
plus `monitoring_status_reason` (`status_history.reason`, where "landowner
asked us to stop" is written down). All six were dropped in the
consolidation; the current value is kept, the history around it is not.

### Permission (current grants)

From `permission_history`, whose `permission_type` lexicon is exactly the three
things a crew does:

| Column | `permission_type` |
| --- | --- |
| `may_measure_water_level` | Water Level Sample |
| `may_sample_water_chemistry` | Water Chemistry Sample |
| `may_install_datalogger` | Datalogger Installation |

**These are three-valued and must stay that way.** `true` = a current grant
says allowed. `false` = a current grant says *not* allowed. `NULL` = **no
permission on record**, which is not the same as denied and must not be
rendered as "no". Collapsing NULL to false would tell a crew a well is off
limits when the truth is that nobody has asked yet; collapsing it to true is
worse. Every consumer-facing rendering of these columns has to carry the third
state.

`permission_granted_by` — the granting contact's name from the current
water-level grant — is published alongside, so a crew can name who said yes.

### Monitoring programme

| Column | Source |
| --- | --- |
| `monitoring_frequency` | current `monitoring_frequency_history` record |
| `group_names` | `group` via `group_thing_association`, joined, de-duplicated |
| `group_types` | Monitoring Plan / Geographic Area / Historical, joined, index-aligned with `group_names` |

`monitoring_frequency_since` (its `start_date`) was dropped in the
consolidation, same as the status `_since` columns above.

### Manual measurement statistics

Manual groundwater levels, reached the way every other water-level view in this
schema reaches them: `observation -> sample -> field_activity -> field_event`,
`field_activity.activity_type = 'groundwater level'`.

| Column | Definition |
| --- | --- |
| `manual_water_level_count` | count of readings with a value and a timestamp |
| `manual_water_level_first_date` | earliest `observation_datetime`, UTC calendar date |
| `manual_water_level_last_date` | latest, UTC calendar date |
| `days_since_manual_water_level` | `CURRENT_DATE - manual_water_level_last_date`, computed in the plain view so it does not freeze at refresh |
| `last_depth_to_water_ft` | the latest reading, below ground surface |

`last_depth_to_water_ft` uses `(o.value - COALESCE(o.measuring_point_height, 0))`
— the reading minus the height of the measuring point above ground, with a
missing height treated as taken at ground level. This is the exact convention
in `ogc_water_well_summary`, `ogc_latest_depth_to_water_wells`, and
`ogc_well_water_column`, and it must stay identical or the four layers will
disagree about what a depth to water is. See
`docs/measuring-point-height-null-handling.md`.

### Chemistry sampling statistics

Same chain, `field_activity.activity_type = 'water chemistry'`:
`chemistry_sample_count`, `chemistry_sample_last_date`,
`days_since_chemistry_sample`. Sample-level, not analyte-level — a crew wants
"when was this well last sampled", not "what was the sulfate".

### Field visit statistics

`field_event_count`, `date_last_visited` from `field_event`
(`field_event_last_date` on the `_stats` matview itself; renamed on the way
out of the feature view to match `thing.first_visit_date`'s counterpart
naming). Broader than either measurement chain: a visit that produced no
reading is still a visit, and the gap between `date_last_visited` and
`manual_water_level_last_date` is itself a signal.

### Data logger / continuous record

**`has_datalogger`/`datalogger_deployment_count` stayed logger-scoped in the
consolidation; every other column in this section was broadened to any
currently-installed sensor.** The original design published only a single
current logger deployment's detail (`datalogger_sensor_type`,
`datalogger_model`, etc., picking the most recently installed one via
`DISTINCT ON` if more than one logger was deployed) and had no way to show a
currently-installed camera, barometer, or weather station at all -- it was
simply invisible. That was a real gap against this layer's own purpose: a
crew visiting a well to swap an SD card or check a barometer's battery needs
to know it is there.

"Has a logger" is still a deployment question, not a sensor-inventory
question: a deployment is current when `installation_date IS NOT NULL` and
`removal_date IS NULL`, and counts towards `has_datalogger` only when the
sensor is one of `Data Logger`, `Pressure Transducer`, `DiverLink`, `Diver
Cable` (`sensor.sensor_type`).

| Column | Definition |
| --- | --- |
| `has_datalogger` | boolean, true when a current *logger* deployment exists |
| `datalogger_deployment_count` | count of current logger deployments only |
| `sensor_type`, `model`, `serial_no`, `sensor_status`, `installed_date`, `recording_interval`, `recording_interval_units`, `hanging_point_desc` | from `sensor`/`deployment` for **every** currently-installed deployment, any sensor type |
| `continuous_reading_count` | rows in `transducer_observation` for this well's deployments |
| `continuous_first_datetime`, `continuous_last_datetime` | series extent |
| `days_since_continuous_reading` | live, in the plain view |

The eight equipment columns are no longer a single row's worth of scalar
values -- a well running more than one current sensor lists all of them,
semicolon-joined, all eight ordered the same way by `sensor_type` so position
N in one list is the same deployment as position N in the others. This
follows the same "comma-joined text, not an array" convention as
`well_purpose`/`well_casing_material` above, with a semicolon instead of a
comma because these columns are genuinely positional across each other, not
independently de-duplicated lists. `recording_interval` is `text`, not
`integer`, as a consequence: `string_agg` always returns `text`, even for a
well with exactly one current sensor.

Every expression but `sensor_type` itself is wrapped in `COALESCE(..., '')`
before aggregating. `sensor_type` is `NOT NULL` on `sensor`, but the other
seven columns are all nullable -- a camera, for instance, has no
`recording_interval` -- and plain `string_agg` silently **drops** a `NULL`
input rather than preserving its position. Caught empirically: a well with a
transducer (`recording_interval = 15`) and a camera (`recording_interval =
NULL`) produced `sensor_type = "Camera; Pressure Transducer"` but
`recording_interval = "15"` -- one segment short, so position 0 read as the
camera's interval when it was actually the transducer's. With the `COALESCE`,
the same well now reads `recording_interval = "; 15"`: an empty segment for
the camera, keeping every column's segment count equal to
`installed_deployments`' row count for that well.

`sensor_status` values are In Service / In Repair / Retired / Lost.
`datalogger_deployment_count` still says how many *logger* deployments are
open, independent of how many total sensors `sensor_type` lists.

`continuous_reading_count` aggregates the largest table in the schema. It is
the reason `_stats` is materialized. If the refresh proves too slow, the
fallback is to source the three continuous columns from `transducer_daily_data`
instead — cheaper, one row per day, and adequate for "is the logger still
reporting".

### Contacts

Subject to §4.

| Column | Definition |
| --- | --- |
| `contact_count` | contacts associated with the well |
| `primary_contact_name`, `_organization`, `_role` | prefer the `contact_type = 'Primary'` contact, else any contact on the well, lowest `contact.id` as tie-break |
| `primary_contact_type` | which of those two cases produced the row above |
| `primary_contact_phone` | lowest-id `phone.phone_number` for that contact |
| `primary_contact_email` | lowest-id `email.email` for that contact |
| `contact_names` | every associated contact, joined |

The fallback is a change from this document's first draft, which took the
primary contact strictly. A well whose only contact is recorded as Secondary
would then show `contact_count = 1` beside a blank name and phone — the exact
failure mode that ruled out option B in §4. `primary_contact_type` keeps the
fallback visible rather than implied.

Deliberately **not** published: `address`. A mailing address is not how a crew
reaches a landowner, and it is the most sensitive field on the record.

### Notes

`notes` is polymorphic on `(target_id, target_table = 'thing')` with a
`note_type` lexicon. The original design published only two operational
types (`access_notes`, `directions_notes`) and kept the rest out, on the
theory that a well's non-visit history is where PII leaks. The consolidation
published a column per remaining `note_type` value instead, same pattern,
most recent first, joined with ` | `:

| Column | `note_type` |
| --- | --- |
| `access_notes` | Access |
| `directions_notes` | Directions |
| `communication_notes` | Communication |
| `construction_notes` | Construction |
| `maintenance_notes` | Maintenance |
| `historical_notes` | Historical |
| `general_notes` | General |
| `water_notes` | Water |
| `water_quality_notes` | Water Quality |
| `sampling_procedure_notes` | Sampling Procedure |
| `coordinate_notes` | Coordinate |
| `owner_comment_notes` | OwnerComment |
| `site_notes_legacy` | Site Notes (legacy) |

Two do not mechanically snake-case: `OwnerComment` has no separator to split
on, so `owner_comment_notes` is a judgment call, not a derivation. `Site Notes
(legacy)` becomes `site_notes_legacy`, not `site_notes_legacy_notes` -- the
term already says "notes".

This does not revisit the PII conclusion in §4 -- if anything it strengthens
it, since these note types are exactly where a landowner's name, a gate code,
or a phone number ends up in free text. See open question 4.

## 7. The "current record" rule

Four histories feed this layer — `status_history`, `permission_history`,
`measuring_point_history`, `monitoring_frequency_history` — and all four have
the same `(start_date, end_date)` shape. One rule for all of them:

```sql
WHERE h.start_date <= CURRENT_DATE
  AND (h.end_date IS NULL OR h.end_date >= CURRENT_DATE)
ORDER BY h.start_date DESC, h.id DESC
LIMIT 1                       -- via DISTINCT ON per thing
```

**This diverges from the existing catalogue on purpose.**
`ogc_actively_monitored_wells` takes the row with the greatest `start_date` and
ignores `end_date` entirely, so a monitoring status that was closed in 2019
still reads as current there. That is tolerable on a summary layer. It is not
tolerable on a layer whose whole job is to tell a crew what is true today —
"you may install a logger here" must not survive the expiry of the permission
that said so.

The divergence has to be written into `docs/ogc_conventions.md`, or the next
person will read the two views side by side and assume one is a mistake.

Rows whose window has not opened yet (`start_date > CURRENT_DATE`) are not
current and read NULL.

## 8. Field-level documentation

`core/ogc_field_metadata.py` keys `core/ogc-field-descriptions.yml` by backing
relation with the `ogc_internal_` prefix stripped, so the entry is
`water_well_field_operations`. This is not optional:
`tests/test_ogc_field_descriptions.py::test_every_published_column_has_an_entry`
walks both mounts and fails on any published column without a `description`.

Columns already in `_defaults` (`id`, `name`, `thing_type`, `release_status`,
`elevation`, `well_depth`, `hole_depth`, `well_casing_diameter`, …) are
inherited and must not be restated. `station_type` needs its own entry despite
being lexicon-governed the same way `thing_type` is, precisely because it is
not named `thing_type` here -- a per-table entry only inherits from
`_defaults` by column name. Everything new to this layer needs an entry, and
the entry says what the value *means*, never how the view is built.

Not every lexicon-governed column carries `enum-lexicon`: the five status
columns use a literal `enum` list instead (pre-dating the consolidation, and
left as-is rather than relitigated here), and `monitoring_frequency`, `role`,
and `contact_type` use `enum-lexicon`. `sensor_type`, `sensor_status`,
`well_purpose`, and `well_casing_material` carry **neither** -- each is an
aggregated, multi-valued column (`string_agg` over more than one row), and an
`enum` on a column whose value can be `"Barometer; Pressure Transducer"` would
be actively wrong, not just incomplete. Depth and height columns carry
`x-ogc-unit: https://qudt.org/vocab/unit/FT` with
`x-ogc-unitLang: QUDT`, matching the rest of the file.

The three permission booleans need their NULL meaning spelled out in the
`description` — that is the only place a consumer will ever read it.

## 9. Wiring

1. **Migration** — new Alembic revision on the current head (`c9d0e1f2a3b4`),
   creating the matview, its unique index, and the view, plus the supporting
   indexes in §10. `downgrade()` drops all three; nothing pre-existing is
   modified, so there is no prior state to restore. Follow the house style in
   `2d3c3a268652`: self-contained, no cross-migration imports, `REQUIRED_TABLES`
   guard up front.
2. **`core/pygeoapi-config-internal.yml`** — one static resource block, next to
   `locations`. `name: core.feature_provider.DescribedPostgreSQLProvider`,
   `id_field: id`, `table: ogc_internal_water_well_field_operations`,
   `geom_field: point`. No `time_field`: no single column is the feature's
   time, and picking one would make `datetime=` filtering quietly mean
   something arbitrary.
3. **`core/pygeoapi-config.yml`** — no change. Ever.
4. **`core/ogc-field-descriptions.yml`** — the `water_well_field_operations` block.
5. **`services/materialized_views.py`** — append
   `ogc_internal_water_well_field_operations_stats` to `MATERIALIZED_VIEWS`.
6. **`core/gis-curated-layers.yml`** — *no* entry. Every layer in that file
   ships as a `.qlr` and a `.lyrx` artifact, and this one is PII-bearing and
   internal; it should be reached by browsing the authenticated connection, not
   handed out as a downloadable file. Revisit only if crews ask.
7. **Docs** — `docs/api-key-management.md` and `docs/internal-ogc-desktop-gis.md`
   gain the PII notice from §4; `docs/ogc_conventions.md` gains the §7
   divergence.

Description text has to clear
`tests/test_pygeoapi_mount.py::test_every_collection_description_explains_the_layer`:
at least 200 characters, ends in a full stop, no placeholder words, no
hyphenated word split across a YAML line break, and at least four unique
lowercase-hyphenated keywords.

## 10. Indexes

The per-thing lookups this layer adds are foreign-key joins, and Postgres does
not index foreign keys on its own. Check each before creating it — `b8c9d0e1f2a3`
already added four on the observation chain.

- `status_history (target_table, target_id, status_type, start_date DESC)`
- `permission_history (target_table, target_id, permission_type, start_date DESC)`
- `measuring_point_history (thing_id, start_date DESC)`
- `monitoring_frequency_history (thing_id, start_date DESC)`
- `notes (target_id, target_table)` — already exists as `ix_notes_polymorphic_link`
- `deployment (thing_id)`
- `thing_contact_association (thing_id)`, `(contact_id)`
- `thing_aquifer_association (thing_id)` — for `aquifer_system_name`, added in
  the consolidation
- `transducer_observation (deployment_id, observation_datetime)` — for the
  continuous aggregates; the largest table in the schema and the one that will
  decide whether the nightly refresh is acceptable

## 11. Settled, and still open

Settled before implementation:

- **"AMP" is a label, not a subset.** The layer covers every water well; there
  is no group predicate.
- **Contact detail is published in full** (§4, option A).

Settled in the consolidation:

- **Access Status has no values -- column removed, not left publishing NULL.**
  `status_type` carried `Access Status`, but the `status_value` lexicon has no
  access-related terms; the eleven values map only to Well, Monitoring, Open,
  and Datalogger Suitability status. Rather than ship a column that could only
  ever read NULL, `access_status` and its join were dropped. `access_notes`
  (§6, Notes) already carries staff-written access information for a well --
  gate codes, locks, who to call -- so nothing a crew needs is lost. If the
  lexicon later gains terms scoped to Access Status, this is worth
  reconsidering, but as a fresh addition rather than un-deleting a column that
  published nothing.

Still open:

1. **Which `thing_type` values count as a well?** Shipped as `'water well'`
   only, for consistency with every existing well layer. If AMP crews also
   visit piezometers and monitoring wells, the predicate widens to a list — and
   then it should widen in the other four layers too, as its own ticket, rather
   than this layer quietly disagreeing with them.
2. **Free-text PII.** All 13 note columns are staff-written and will contain
   phone numbers, gate codes, and names -- more of them since the
   consolidation, which published the eleven note types the original design
   deliberately kept out (§6, Notes). A further reason the layer is
   internal-only, and the §4 decision covers them too.
3. **Refresh cadence.** Nightly, via the existing pg_cron job. If crews plan
   the next day's route the evening before, nightly is fine; if they re-plan in
   the field, the stats columns are the ones that go stale.
4. **`continuous_reading_count` cost at production scale.** It aggregates the
   largest table in the schema. If the nightly refresh proves too slow, the
   fallback is to source the three continuous columns from
   `transducer_daily_data` instead.

## 12. Out of scope

- Any public counterpart.
- Write access. This is a read layer; edits happen in the Ocotillo UI.
- A curated `.qlr` / `.lyrx` artifact (§9.6).
- Springs and other non-well monitoring points.
- Per-field authorization. pygeoapi has no such hook; the layer boundary is the
  authorization boundary.
