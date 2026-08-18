# Source: San Acacia Reach (Van Essen divers, Diver-HUB)

The pilot source for automated ingestion: 33 monitoring points, one
depth-to-groundwater series each. Historically flowed through the retired
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

### Windowing

`WaterLevels`, `DiverData`, `ManualMeasurements` and `AirPressure` all take
`startTime` and `endTime` as **Unix seconds, UTC**, inclusive of both ends.

An oversized span returns **HTTP 500** — not a 413, not a pagination cursor.
The 500s that stalled this work were this, not a vendor outage. A
confirmed-good request:

```
GET /DiverData/ByMonitoringPoint/40?startTime=1767225600&endTime=1775001600
```

That is roughly 1 Jan – 1 Apr. Consequently a fetch is always a sequence of
bounded windows, and the right response to a 500 is to halve the window and
retry rather than to mark the entity failed. This applies to the daily
incremental run too, not only to backfill: an entity whose cursor has fallen
months behind hits the same ceiling. See `automated_ingestion/shared/windows.py`.

**The exact ceiling is unmeasured.** Three months works. `probe_diverhub.py`
widens until it breaks; record the result here when it has been run.

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

### WaterLevelReference — unresolved, and the highest-risk unknown here

The swagger declares:

```json
"WaterLevelReference": { "enum": [0, 1, 2, 3] }
```

No names, no descriptions. **Which value means depth below ground surface
cannot be determined from the specification.**

This matters more than the other open questions because getting it wrong does
not fail. It returns plausible numbers on the wrong datum, and every ingested
reading is silently wrong. `GROUND_SURFACE_REFERENCE` in `client.py` is
therefore `None`, and the pipeline refuses to guess.

Resolve it by running `probe_diverhub.py`, which samples all four values for
one point side by side, and comparing against a well whose depth to water is
independently known. Record the answer here and set the constant.

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
| 2 | What is the window ceiling? | `probe_diverhub.py` widens until 500 |
| 3 | Which project id holds San Acacia, and is it really 33 points? | `probe_diverhub.py` |
| 4 | Do `approved=true` and `approved=false` partition the series, or overlap? | Fetch both for one window and compare timestamps |
| 5 | Is `dateAndTime` UTC in the response, and is it marked as such? | Inspect a live payload |
| 6 | Is `level` in feet? | Compare against a known measurement |

Questions 1 and 6 both gate correctness rather than completeness: wrong answers
produce data that looks fine.
