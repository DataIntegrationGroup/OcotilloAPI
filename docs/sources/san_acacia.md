# Source: San Acacia Reach (Van Essen divers, Diver-HUB)

The pilot source for automated ingestion. Project **4317 `SanAcaciaReach`**,
containing **38 monitoring points** named `SO-####` — the plan and the Aqueduct
mapping both say 33, so five are unaccounted for and must be identified before
3.2 reconciles anything. Ingestion never creates wells, so an unexpected point
is a decision, not a row. Historically flowed through the retired
FROST/`st2` stack; now flows nowhere.

This document supersedes the mapping in `Aqueduct/docs/sources/san_acacia.md`,
which described the FROST-era payload rather than the live API.

## API

Base URL `https://diver-hub.com/private/api/v1`.
Specification: `https://diver-hub.com/private/swagger/v1/swagger.json` — public,
no authentication needed to read it. **Treat the swagger as authoritative over
anything inherited from the FROST pipeline.**

There is no `/api/api/` doubled path segment and no `locations/sanacaciareach`
endpoint. Both appeared in earlier drafts and neither exists.

| Endpoint | Returns | Used for |
|---|---|---|
| `POST /Accounts/Login` | `{token, validTo}` | Authentication |
| `GET /Projects` | `[{id, name}]` | Finding the San Acacia project id |
| `GET /MonitoringPoints/ByProject/{projectId}` | `[{id, name}]` | The 33 points |
| `GET /WaterLevels/ByMonitoringPoint/{id}` | `[{dateAndTime, level}]` | **The series we ingest** |
| `GET /DiverData/ByMonitoringPoint/{id}` | `[DataPoint]` | Raw sensor output; not ingested |
| `GET /ManualMeasurements/ByMonitoringPoint/{id}` | `[{dateAndTime, waterLevelToc}]` | Not ingested — see below |
| `GET /WeatherStationData/AirPressure/ByMonitoringPoint/{id}` | `[DataPoint]` | Not ingested |

### Authentication

`POST /Accounts/Login` with `{username, password}` returns a bearer JWT and a
`validTo` timestamp. Every other endpoint requires
`Authorization: Bearer {token}` and answers `401` without it.

The token is short-lived — about an hour. Refresh against `validTo` rather than
against an assumed lifetime, with a skew so a request in flight at the boundary
does not arrive expired, and re-authenticate once on a `401` so a clock
difference cannot end a backfill. Implemented in
`automated_ingestion/sources/san_acacia/client.py`.

Credentials live in Secret Manager, never in GitHub secrets and never in the
repository. They are read from `DIVERHUB_USERNAME` / `DIVERHUB_PASSWORD`.

### Windowing — measured 2026-08-18

All series endpoints take `startTime` and `endTime` as **Unix seconds, UTC**,
inclusive of both ends.

**The 500 is endpoint-specific, and `WaterLevels` — the endpoint we ingest —
did not exhibit it.** Measured against point 39 (SO-0125):

| Span back from now | `WaterLevels` |
|---|---|
| 90 d | ok, 0 rows |
| 180 d | ok, 1054 rows |
| 365 d | ok, 1054 rows |
| 545 d | ok, 9302 rows |
| 730 d | ok, **18111 rows** |

A fixed 30-day window slid back 0/1/2/3 years also succeeded every time, so
there is no age-based cutoff on this endpoint either.

`DiverData` is a different story: a 730-day request failed, and bisecting it
ten times down to a **17-hour** window still returned 500. That is not a volume
ceiling — a 17-hour window of raw diver data is trivial. The failing slice was
the oldest part of the range, starting 2024-08-18. Whatever the cause, it is
specific to `DiverData`, which we do not ingest.

Practical consequence: the windowing machinery in
`automated_ingestion/shared/windows.py` stays, because 18111 rows in one
response is already large and the ceiling is untested above 730 days, but the
halve-on-500 recovery is **not** a routine path for `WaterLevels`. Do not
assume a 500 there means "too much data" without re-measuring; on `DiverData`
that assumption is provably wrong.

## Field mapping

### Water levels — the ingested series

`WaterLevel` is `{dateAndTime: date-time, level: double}`. That is the whole
schema. Two consequences worth stating plainly, because earlier drafts assumed
otherwise:

- **There are no `gs` / `vrd` arrays**, and no `approvedWaterLevelsGs` /
  `unApprovedWaterLevelsGs`. Nothing in the response says which datum `level`
  is on or whether the vendor approved it.
- **Datum and approval are request parameters.** `reference` selects the datum;
  `approved` (boolean) selects the vendor's approval state. The same point and
  time range returns different numbers depending on what was asked for.

### WaterLevelReference — measured, not yet decided

The swagger declares `"WaterLevelReference": { "enum": [0, 1, 2, 3] }` with no
names and no descriptions, so the meaning cannot be read off the spec.

Sampled for SO-0125 over 365 days — all four return **the same 1054 rows at the
same timestamps**, differing only by a constant offset. They are one series
expressed against four datums:

| `reference` | min | max | offset vs 0 |
|---|---|---|---|
| 0 | 199.356 | 250.697 | — |
| 1 | 267.462 | 318.804 | +68.11 |
| 2 | 139200.653 | 139251.994 | +139001.30 |
| 3 | 222.005 | 273.347 | +22.65 |

Spread is identical to three decimals (51.34) across all four, confirming they
are the same measurements re-referenced.

**`reference=2` is an elevation, not a depth.** It is three orders of magnitude
larger than the others. Read as centimetres it is 1392 m ≈ 4567 ft, which
matches San Acacia's ground elevation — which in turn implies the unit
throughout is **centimetres**, making 0/1/3 read as roughly 2–3 m depths.
That is plausible for riparian piezometers and implausible as feet, but it is
inference from one well, not a confirmed unit.

**Which of 0, 1, 3 is ground surface is still undecided**, and min/max cannot
settle it. `GROUND_SURFACE_REFERENCE` stays `None`.

Two things resolve it, both automated in `probe_diverhub.py`:

1. **Aligned-row comparison.** An elevation moves opposite to a depth, so
   `elevation + depth` is constant while `depth − depth` is constant. Comparing
   rows at the same timestamp separates them; comparing ranges cannot, because
   an inversion and an offset produce the same spread.
2. **`ManualMeasurements` as ground truth.** It reports `waterLevelToc` —
   explicitly top of casing. Whichever reference tracks it *is* the TOC series,
   and ground surface is the one shallower by the casing stickup. The +68.11
   gap between references 0 and 1 is a plausible stickup (~0.7 m), which makes
   that pair the likely GS/TOC candidates — but "likely" is not good enough for
   a datum, since a wrong choice produces plausible numbers rather than an error.

### Monitoring points — thinner than expected

`MonitoringPoint` is `{id: int, name: string}`. **No coordinates, no
`drillingDepth`, no construction detail.**

So the planned `drillingDepth` centimetre conversion (÷ 30.48) has no source in
this API, and neither does geometry. Both have to come from the Ocotillo
`Thing` and `Location` records the points reconcile against. That is consistent
with the decision that ingestion never creates wells: matching to an existing
row is the only way it learns where a point is.

### Not ingested

- **`DiverData`** returns `DataPoint` — `pressure`, `temperature`,
  `conductivity`, `salinity`, `airPressure`, `precipitation`. Useful for
  diagnostics, and it is what the known-good example URL fetches, but it
  contains no water level.
- **`ManualMeasurements`** returns `waterLevelToc` — top of casing. Ocotillo's
  manual-measurement path already owns this, and mixing a TOC-referenced series
  into a ground-surface one is the datum error above by another route.
- **`AirPressure`** matters only for barometric compensation, which is the
  Hydrograph Corrector's job downstream.

## Decisions inherited from the epic

Settled, not to be relitigated per source:

- **Ground-surface datum.** Never `vrd`, never TOC. No measuring-point
  correction on ingest.
- **Public but provisional.** Visible from the first run, marked so no consumer
  mistakes an uncorrected diver series for a reviewed one.
- **The vendor `approved` flag is not Ocotillo `review_status`.** Ocotillo's
  `approved` asserts a *Bureau* human reviewed it and carries a `reviewer_id`
  FK. All San Acacia blocks land `not reviewed`; the vendor flag is preserved
  as a separate per-row attribute.

## Open questions

| # | Question | How to settle |
|---|---|---|
| 1 | Which `reference` value is ground surface? | `probe_diverhub.py`, compared against a known well |
| 2 | ~~What is the window ceiling?~~ | **`WaterLevels` took 730 d / 18111 rows. The 500 is a `DiverData` problem** |
| 3 | ~~Which project id, how many points?~~ | **Answered: 4317, 38 points (not 33)** |
| 4 | Do `approved=true` and `approved=false` partition the series, or overlap? | Fetch both for one window and compare timestamps |
| 5 | Is `dateAndTime` UTC in the response, and is it marked as such? | Inspect a live payload |
| 6 | Is `level` in feet? | Compare against a known measurement |

Questions 1 and 6 both gate correctness rather than completeness: wrong answers
produce data that looks fine.
