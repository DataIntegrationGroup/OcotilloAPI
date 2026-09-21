# Hydrograph correction — publish, range delete, and single readings

The hydrograph corrector in OcotilloUI (`/ocotillo/hydrograph-correction`)
ingests a raw logger file, converts water head to depth below ground surface
against manual measurements, applies corrections, and publishes the result
here. This document records what the API side actually does; the UI-side
proposal it was built from is
`OcotilloUI/docs/hydrograph-correction-upload-contract.md`.

## Authorization

Every write route — publish, range delete, and the per-reading edit and delete —
is gated on **`AMP.Admin`** (`amp_admin_dependency`). Both reads, the list and
the single reading, stay on `amp_viewer_dependency`: publishing does not change
who may look.

The publish and range-delete routes shipped dark behind a standalone
`AMP.Staging` group while the workbench was validated against real logger
files. That group is gone. It was never a tier, so retiring it was a one-line
change per route rather than a change to the AMP ladder.

The whole AMP family went dotted at the same time — `AMP.Admin`, `AMP.Editor`,
`AMP.Viewer` replaced `AMPAdmin`, `AMPEditor`, `AMPViewer` — matching the names
OcotilloUI already uses. Production Authentik must carry the dotted groups with
the old groups' members before this deploys, or every AMP user loses access.

## `POST /observation/transducer-groundwater-level/block`

One corrected logger file becomes one block plus all of its readings, in one
transaction.

- **The span is derived, not sent.** `start_datetime`/`end_datetime` come from
  the min/max measurement timestamp. A client-supplied span wider than the data
  would make the block claim readings it does not contain, because nothing links
  the observation table to the block table — the reader pairs them by time.
- **`deployment_id` is optional.** Omitted, it is resolved from the deployments
  on the well whose installation period covers the span. A NULL installation date
  reads as "always installed", a NULL removal date as "still installed". Zero or
  more than one match is a 422 telling the client to send it explicitly, because
  guessing attributes readings to hardware that did not record them.
- **`data_maturity` is derived from `review_status`**, not sent: a block
  published as `not reviewed` is `provisional` on USGS terms. Sending both
  separately would let a client store a contradiction.
- **Provenance is part of the record.** `source_file`, `source_kind`, and the
  ordered `corrections` list live on the block; `provenance.notes` lands in the
  block's existing `comment`. A reviewer who cannot see that a series was
  snapped to a manual measurement cannot review it.
- **Per-reading `note`** is set only where a correction moved the value, so NULL
  means "as measured" rather than "unknown".

- **`parameter_id` is validated, not obeyed.** The client states it explicitly,
  per the contract, but the route checks it against the parameter the route is
  scoped to. The read and delete routes on this path resolve groundwater level
  themselves, so a block accepted under any other parameter would be a 201 for
  data neither of them could ever list or remove.

### Concurrency

Both write paths read state, decide, and then write based on what they read, so
each takes a transaction-scoped advisory lock on `(thing_id, parameter_id)`
first — `pg_advisory_xact_lock`.

Without it, two publishes with different timestamps but overlapping spans each
see no existing block and both commit: the unique constraints only catch
identical spans and identical readings, and the inclusive reader then has two
blocks claiming the same instants. Two range deletes each compute survivors from
a snapshot the other is invalidating, and the later update can widen a block back
over readings the earlier one removed.

An advisory lock rather than row locks because on publish there is no row to
lock — the conflict is with a block that does not exist yet — so what needs
guarding is the series, not a row. Both paths take the same key, so they
serialize against each other and cannot deadlock against one another.

### Overlap

An existing block for the same well and parameter whose span shares any instant
with the new one is a **409** listing the collisions in
`detail[0].input.overlapping_blocks`. `?replace_overlapping=true` deletes those
blocks **and their readings** in the same transaction and then publishes.

The readings have to go with the block. Keeping them would leave rows the reader
cannot show — no block covers them — that still occupy the
deployment/parameter/instant the new series is about to claim, so a "replace"
that kept them would fail on the very insert it was asked to make room for.

Overlap here is **inclusive on both bounds**, unlike
`TransducerObservationBlock.overlaps` on the model, which is half-open. The
reader matches a reading to a block with `start <= t <= end`, so two blocks
sharing an endpoint both claim any reading at that instant — exactly the
ambiguity this check exists to prevent.

Readings can also survive a block deleted by hand. Those are caught separately
and reported as a 409 naming the earliest colliding timestamp, rather than
letting the insert abort the transaction with a constraint name.

## `DELETE /observation/transducer-groundwater-level`

`thing_id`, `start_time`, and `end_time` are all required. There is deliberately
no unbounded form of this request. The scope matches the `GET` on the same path
exactly, so the set a client previews is the set this removes.

Blocks are reconciled afterwards: one left with no readings is deleted, one left
with some has its span narrowed to the survivors. A block narrowed to a single
reading becomes zero-width, which the `end_datetime >= start_datetime` check
constraint allows on purpose (migration `c3d4e5f6a7b8`) and which the inclusive
reader still covers.

That same migration renames the constraint from `check_transuder_...` to
`check_transducer_...`. Postgres cannot alter a check in place, so the
drop-and-recreate the relaxation already required was the free moment to fix
the spelling. The downgrade puts the old name back, so anything reaching for
the constraint by name has to pick the spelling that matches the revision it is
running against.

**This leaves the `transducer_daily_data` materialized view stale** until its
next scheduled refresh. Nothing here refreshes it — a full refresh on every
delete would cost far more than the correctness it buys between nightly runs.

## Single readings — `/observation/transducer-groundwater-level/{observation_id}`

`GET`, `PATCH`, and `DELETE` address one reading by id. All three are scoped to
the groundwater level parameter the same way the list is: a reading under any
other parameter is a 404, so an id cannot reach data the list would never show.

### `GET`

Returns the reading, the block covering it, and the well. The block is chosen
exactly as the list chooses it — inclusive on both bounds, latest-starting
block first.

`block` is **null** for a reading no block covers. The list never shows those,
since it pairs every row with a block; they are what a block deleted by hand
leaves behind. Addressed by id, reporting one as missing would hide a row that
still exists and still holds its deployment/parameter/instant — the same row
publish's collision check will later refuse to write over.

### `PATCH`

Edits `value`, `note`, `data_maturity`, and `release_status`. Nothing else.

- **The timestamp, deployment, and parameter are not editable.** Only time ties
  a reading to its block — there is no foreign key between the tables — so
  moving a reading would drop it out of its block, where the list cannot see
  it, or slide it under a different block. The schema forbids extra fields, so
  sending one is a 422 rather than a silent no-op. Moving a reading is a delete
  and a republish.
- **A changed `value` needs a `note`.** A NULL note means "as measured", which a
  hand-edited value is not. The check is on the note the row would end up with,
  so a reading a correction already annotated takes a new value without a new
  note.
- **`value` and `release_status` cannot be sent as null.** Omitting a field
  leaves it alone; an explicit null on a required column would fail as a 500.

It takes the series lock too. An edit moves no span, but without the lock it
could land on a row a concurrent delete is removing, and that surfaces as a
stale-row 500 instead of a 404.

### `DELETE`

Deletes the one row and reconciles the block that covered it with the same
function the range delete uses: a block left with no readings is deleted, one
left with some is narrowed to the survivors. The response is the range delete's.

This is not the same as a range delete over the reading's instant. A range is
scoped to the well, so it would also take a second sensor's reading at that
instant; this takes only the row named.

It leaves `transducer_daily_data` stale, as the range delete does.

## Two things fixed in passing

- The read route was calling `get_transducer_observations` positionally, and the
  helper's fourth positional parameter is `sensor_id`. `start_time` was landing
  in `sensor_id` (unused, silently dropped), `end_time` was landing in
  `start_time`, and `end_time` was never set — so an upper bound a caller asked
  for was ignored and the lower bound came from the wrong argument. The call is
  keyword-only now.
- The read route honours `sort` (`observation_datetime`, `value`, `id`) and
  `order` (`asc`/`desc`), defaulting to newest first. An unrecognised sort field
  or order is a 422 rather than being ignored — silently returning a differently
  ordered page reads as the data changing, not as a bad request. `order` matters
  particularly here: anything other than `asc` used to fall through to
  descending, so the near-miss `order=ascending` returned 200 with the rows in
  exactly the opposite order to the one asked for.

## Not built

Everything in the contract's "Supporting endpoints for Wellntel ingestion"
section is deferred: the `GET /wellntel/readings` proxy and the `sensor_type`
filter on `GET /thing`. Both are blocked on open questions the contract itself
raises — where the Wellntel API key lives and where the wellname→PointID mapping
belongs. The UI already falls back to demo data when they are absent.

Also open, and unchanged by this work: whether the raw water-head series should
be retained alongside the corrected one, and whether publishing as `provisional`
should feed a review queue.
