# Embargoing data until a date

An embargo is a record withheld from public release until a date decided in
advance. It is two columns on every `ReleaseMixin` table:

| column | meaning |
| --- | --- |
| `release_status = 'embargoed'` | the record is being withheld |
| `release_at` | the date it becomes public |

When the date arrives, `oco release-embargoed --apply` flips the level to
`public`. The record then appears in the public OGC collections on their next
refresh.

## The two rules worth knowing before you touch this

**`release_at` is intent. `release_status` is enforcement.** Nothing on the
read path consults `release_at` — not the OGC views, not the API, not the
visibility layer. It exists so a job can change `release_status` on the right
day. If you find yourself adding a date comparison to a read path, stop: that
is the distributed filtering ADR5 exists to prevent, and migration
`baba91fe5e83` is what it already cost this repository once.

**An embargo only ever widens visibility.** The scheduled path turns
`embargoed` into `public`, and does nothing else. Withdrawing something already
published is an immediate change to `release_status`, made by a person — never
scheduled. This mirrors `domain/access.py`, where a revocation takes effect at
once and is never backdated: a promise to hide something *later* is not a
promise anyone should rely on.

## Why a job and not a predicate in the views

The obvious design is `WHERE release_at IS NULL OR release_at <= current_date`
in the OGC views, so that no job is needed and the embargo lifts itself at read
time. It was rejected.

Seven of the public collections are **materialized** views, refreshed by one
pg_cron job at 09:00 UTC (`docs/pg_cron-nightly-refresh.md`). `current_date`
inside a materialized view is frozen at refresh time. A date predicate would
therefore buy nothing on more than half the public surface, while costing a
recreation of every relation that carries it. The refresh already sets the
granularity, so the cheaper mechanism with the same behaviour wins.

Consequence to be honest about: **an embargo lifts up to a day late**, bounded
by when the release job and the refresh run. It never lifts early.

## Running it

```bash
oco release-embargoed
```

Previews by default, like `oco seed-access-grants`; add `--apply` to write.
Idempotent — a released record is no longer embargoed, so a second run finds
nothing. Every flip writes an `authorization_audit` row recording the date the
embargo was set for alongside the date it was actually lifted, so "was this
released early" stays answerable.

**Ordering matters.** Run it *before* the 09:00 UTC materialized-view refresh.
A record released after the refresh waits another day to appear.

### It is not scheduled yet

The CLI exists; nothing runs it on a timer. Until that is wired, an embargo
lifts when someone runs the command. Two ways to wire it, neither free:

- **App Engine cron / Cloud Scheduler → an HTTP route.** Fits the existing
  deployment, but means adding a route whose effect is publishing data. That
  route needs its own authorization decision — `X-Appengine-Cron` alone is a
  header, not an authenticator, once anything else can reach the app.
- **pg_cron, next to the refresh job.** The scheduler is already there and the
  ordering would be trivial to guarantee. But pg_cron cannot call Python, so
  the flip would have to be reimplemented in SQL — a second copy of the rule,
  which is the drift this repository has already paid for once.

Failure in either direction is safe: if the job does not run, embargoed records
stay embargoed.

## What is enforced, and where

Migration `b4c5d6e7f8a9` adds the embargo clause to the four public relations
that read the observation chain:

- `ogc_water_well_summary`
- `ogc_water_elevation_wells`
- `ogc_depth_to_water_trend_wells`
- `ogc_latest_depth_to_water_wells`

The clause is `release_status IS DISTINCT FROM 'embargoed'`, applied at each
level of the chain — observation, sample, field activity, field event — so an
embargoed reading cannot be reached through a public parent. `IS DISTINCT
FROM` rather than `<>` because `release_status` is nullable and `NULL <>
'embargoed'` is NULL, which would drop the row.

`ogc_well_water_column` and the Group A thing views need no change: they
already filter their observations on `release_status = 'public'`, which
excludes `embargoed` for free. Whole-thing embargoes need no change anywhere,
for the same reason.

The `ogc_internal_*` mount is deliberately untouched. It serves Bureau staff
and has never filtered on release level; seeing embargoed data before it is
published is what it is for.

### Why the clause is not `= 'public'`

Matching the other relations would be tidier, and is deliberately not done. It
would also drop every observation sitting at `draft`, `provisional`, or NULL —
a release-policy change with its own row counts to check, not an embargo. As
written, the four relations returned byte-identical results the day the
migration landed, because nothing was embargoed yet.

Migration `w1x2y3z4a5b6` is the record of what the tidier version costs when
the row states are not what you assumed: three NGWMN exports emptied outright,
3005/3005 rows on one of them. If someone later decides the public relations
should require `= 'public'` all the way down, that is its own change, with row
counts taken on a prod clone before and after.

## Chemistry cannot be embargoed per record

`ogc_major_chemistry_results`, `ogc_minor_chemistry_wells`,
`ogc_avg_tds_wells` and `ogc_latest_tds_wells` do not read `observation` and
`sample`. They read the legacy `NMA_Chemistry_SampleInfo`,
`NMA_MajorChemistry` and `NMA_MinorTraceChemistry` mirror tables, which are
plain `Base` models carrying no release columns at all — no `release_status`,
no `data_maturity`, no `release_at`. Their only gate is the joined thing.

So chemistry can be embargoed **per well**, by embargoing the thing, and not
per result. Since chemistry is the usual reason anyone wants an embargo, this
is the gap to close first. Three ways, none cheap:

1. **Release columns on the `NMA_*` mirrors.** They are deprecated and frozen
   (`transfers/README.md`), and repopulated by a deprecated driver that would
   have to learn to preserve a governance column it knows nothing about. Key
   anything added there on `nma_global_id`, which is stable and UNIQUE — never
   the autoincrement `id`.
2. **An embargo side-table** keyed by `nma_global_id`, joined into the four
   views. Leaves the frozen tables alone, at the cost of governance living in
   two places, which is what ADR5 exists to stop.
3. **Wait for chemistry to move onto the Ocotillo `observation` model.** Then
   it joins the chain above and costs nothing. Not currently scheduled.

## Files

| file | what it holds |
| --- | --- |
| `domain/release.py` | the rules, over plain values, no database |
| `services/release_schedule.py` | loads due rows, flips them, writes the audit |
| `cli/cli.py` (`release-embargoed`) | the command |
| `db/base.py` (`ReleaseMixin`) | the `release_at` column |
| `alembic/versions/a3b4c5d6e7f8_*` | the column, on 35 tables and 7 version tables |
| `alembic/versions/b4c5d6e7f8a9_*` | the embargo clause in the four public views |
| `tests/test_ogc_embargo.py` | the claim, checked against the relations themselves |
