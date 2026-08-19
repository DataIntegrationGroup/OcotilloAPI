# Source: San Acacia Reach (Van Essen divers, Diver-HUB)

The pilot source for automated ingestion. Project **4317 `SanAcaciaReach`**,
containing **38 monitoring points** named `SO-####`.

**On the "33 wells" figure.** Earlier drafts of the plan said 33 and treated 38
as a discrepancy to resolve. It is not one. The number came from Aqueduct's
`docs/sources/san_acacia.md`, in a sentence describing an endpoint that no
longer exists:

> Pagination: none — `/locations/{projectName}` returns all 33 wells in one response.

That document is also where the doubled `/api/api/` path, the claim that the
source is unauthenticated, and the `gs`/`vrd` array payload came from — all four
disproved against the live API. The count has no more standing than the rest of
it: a FROST-era snapshot, not a Bureau record of how many wells the reach has.

**38 is the live count.** Whether all 38 are in scope — some may be
decommissioned, or belong to a neighbouring project — is a question about the
well inventory, and the reconciliation report answers it concretely, per well,
rather than by arguing about a total. Historically flowed through the retired
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

## Raw zone format

Parquet, date-partitioned:

```
raw_sanacaciareach/vanessen_readings/year=2026/month=08/day=19/<load_id>.<file_id>.parquet
```

dlt writes gzipped JSONL unless told otherwise, and the first live run landed
that way before this was set. Parquet is what Mode B replay assumes: replay
reads the raw zone filtered on event time, and a columnar format with real types
lets it read a window without decompressing and parsing every record.

Objects written before this change are `.jsonl.gz`. dlt reads both, so they do
not need migrating, but a replay spanning that boundary reads two formats.


## Retention and the gap in the record

Diver-HUB serves nothing before late 2024. Probing six points put their earliest
reading at **2024-10-08** and **2024-11-10** — matching the deployments on these
wells, installed **2024-11-25**. The vendor project was populated then.

Ocotillo already holds AMPAPI transducer data for fourteen of these wells,
ending **2022-08-03**.

**So the two sources never overlap, and roughly twenty-seven months are missing
from the record.** That gap cannot be filled from Diver-HUB. If the divers were
logging through it, the readings are somewhere else.

Two consequences:

- **The datum comparison is impossible.** Comparing the vendor's readings
  against Ocotillo's existing values at matching timestamps was the plan for
  confirming `reference=3` against real data. There are no matching timestamps.
  Attempted on SO-0125 (Feb 2022) and SO-0245 (Jul–Aug 2022); the vendor
  returned zero rows for both windows at every reference. The case for
  `reference=3` therefore rests on the probe evidence — the elevation
  cross-check and the 1.49 ft stickup — not on agreement with what is stored.
- **No datum mixing can occur on a normal run.** Each series resumes from its
  own watermark, and the vendor has nothing to return before 2024, so the two
  bodies of data stay separate by construction rather than by care.

`INITIAL_START` is 2024-01-01 as a result: nine months of margin below the
earliest observed reading, since only six of thirty-eight points were probed.
That takes a first run from twelve windows per well to three — 228 requests
across all thirty-eight instead of 912.

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

### WaterLevelReference — resolved 2026-08-18

The swagger declares `"WaterLevelReference": { "enum": [0, 1, 2, 3] }` with no
names, so this was determined by measurement.

All four values return **the same rows at the same timestamps**, related by
constants that held identically across two windows eighteen months apart:

```
ref1 + ref0 = 518.160        ref3 + ref0 = 472.704        ref2 - ref0 = 139001.296
```

A constant *sum* means the two move in opposite directions; a constant
*difference* means they move together. So `ref0` and `ref2` rise with the water
and `ref1`/`ref3` fall — the latter pair are depths. `ref1` is deeper than
`ref3` by a fixed **45.456 cm (1.49 ft)**, which is a casing stickup.

| Value | Meaning | Ingested |
|---|---|---|
| 0 | Water height above the diver | No |
| **3** | **Depth below ground surface** | **Yes** |
| 1 | Depth below top of casing | No |
| 2 | Water-surface elevation above sea level | No |

`GROUND_SURFACE_REFERENCE = 3`.

Sample values for SO-0125, 2024-10-30T20:00:00Z:

| ref0 | ref1 | ref2 | ref3 |
|---|---|---|---|
| 1.186 | 516.974 | 139002.482 | 471.518 |

The reading checks out physically. The sensor sits at 1390.01 m; ground surface
is 4.727 m above it at **1394.74 m (4576 ft)**, right for San Acacia. Depth to
water runs 4.72 m in October 2024 to 2.2–2.7 m in April 2026, right for a
riparian piezometer.

**Not independently corroborated.** `ManualMeasurements`, which reports
`waterLevelToc` explicitly, returned nothing in the sampled window, so `ref1`
being TOC is inferred from the stickup rather than confirmed against a measured
one. The probe now searches ten years for a manual reading; a single one would
close this.

### Units — centimetres, not feet

`ref2` is only an elevation if the unit is centimetres: 139002 cm is 1390 m,
which matches San Acacia, whereas any other unit puts the ground somewhere
impossible. That fixes the unit for every value the API returns.

**Ocotillo stores feet.** Convert with `domain.units.convert_cm_to_ft`
(`/100 * 3.28084`). An unconverted value is wrong by a factor of 30.48 and
still reads as a plausible depth, so it would survive review.

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
| 1 | ~~Which `reference` value is ground surface?~~ | **Answered: 3.** Corroboration via `ManualMeasurements` still outstanding |
| 2 | ~~What is the window ceiling?~~ | **`WaterLevels` took 730 d / 18111 rows. The 500 is a `DiverData` problem** |
| 3 | ~~Which project id, how many points?~~ | **Answered: 4317, 38 points. The 33 was a stale figure, not a discrepancy** |
| 4 | Do `approved=true` and `approved=false` partition the series, or overlap? | Fetch both for one window and compare timestamps |
| 5 | Is `dateAndTime` UTC in the response, and is it marked as such? | Inspect a live payload |
| 6 | ~~Is `level` in feet?~~ | **No — centimetres.** Convert with `convert_cm_to_ft` |

Questions 1 and 6 both gate correctness rather than completeness: wrong answers
produce data that looks fine.
