# Hydrograph correction — publish and range delete

The hydrograph corrector in OcotilloUI (`/ocotillo/hydrograph-correction`)
ingests a raw logger file, converts water head to depth below ground surface
against manual measurements, applies corrections, and publishes the result
here. This document records what the API side actually does; the UI-side
proposal it was built from is
`OcotilloUI/docs/hydrograph-correction-upload-contract.md`.

## Authorization

Both write routes are gated on **`AMP.Staging`**, a standalone Authentik group.
It is not a fourth rung on the AMP ladder: `AMPAdmin` does not satisfy it, and
it satisfies nothing else. Nobody holds it until it is granted, so the routes
ship dark and are reachable only by whoever is validating the workbench against
real logger files.

When the workbench is trusted, these routes move to `amp_admin_dependency` and
the group goes away. Leaving it as a tier would make that a schema change
instead of a one-line edit.

The read route stays on `amp_viewer_dependency` — it was already public to
viewers and publishing does not change who may look.

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

## Two things fixed in passing

- The read route was calling `get_transducer_observations` positionally, and the
  helper's fourth positional parameter is `sensor_id`. `start_time` was landing
  in `sensor_id` (unused, silently dropped), `end_time` was landing in
  `start_time`, and `end_time` was never set — so an upper bound a caller asked
  for was ignored and the lower bound came from the wrong argument. The call is
  keyword-only now.
- The read route honours `sort` (`observation_datetime`, `value`, `id`) and
  `order` (`asc`/`desc`), defaulting to newest first. An unrecognised sort field
  is a 422 rather than being ignored — silently returning a differently ordered
  page reads as the data changing, not as a bad request.

## Not built

Everything in the contract's "Supporting endpoints for Wellntel ingestion"
section is deferred: the `GET /wellntel/readings` proxy and the `sensor_type`
filter on `GET /thing`. Both are blocked on open questions the contract itself
raises — where the Wellntel API key lives and where the wellname→PointID mapping
belongs. The UI already falls back to demo data when they are absent.

Also open, and unchanged by this work: whether the raw water-head series should
be retained alongside the corrected one, and whether publishing as `provisional`
should feed a review queue.
