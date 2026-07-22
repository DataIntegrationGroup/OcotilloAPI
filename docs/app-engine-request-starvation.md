# App Engine Request Starvation — Outage and Fix

## Summary

On 2026-07-06 the production App Engine service `ocotillo-api` returned
site-wide `500`/`503` errors for **every** endpoint, including `/` and
`/health`. The application itself was healthy — requests were being killed in
App Engine's pending queue before they ever reached the app, because the
scheduler was not scaling out under burst load. The fix caps per-instance
concurrency so App Engine scales out sooner, keeps one instance warm, and
raises per-instance worker count.

## Symptoms

- `500`/`503` on all routes, including trivial ones (`/`, `/health`).
- In Cloud Logging, the failing `RequestLog` entries had:
  - status `500`/`503`,
  - latency ~`0.002s`,
  - a **blank `instanceId`**.

  A blank `instanceId` means App Engine never assigned the request to an
  instance — it died in the pending queue, not in application code.
- Over one ~54-minute window: **279 of 300** requests were `500` with a blank
  `instanceId`. The **21** requests that did reach an instance all returned
  `200` in ~0.1s.
- Only **one** instance was ever serving, despite `max_instances: 10`.
- No `Exceeded soft memory limit` lines (not OOM) and no application
  tracebacks on the failing requests (not a code crash).

## Root cause

The service runs under Gunicorn with Uvicorn workers:

```
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

Real per-instance concurrency is therefore **4** (four worker processes).

App Engine's `automatic_scaling` block did **not** set
`max_concurrent_requests`. Without it, the scheduler assumes an instance can
absorb far more concurrent requests than the four workers can actually serve.
Under a burst — the map UI fires many
`?f=json&limit=10000` collection requests at once, each a multi-second,
10,000-feature GeoJSON serialization — the scheduler kept routing to the one
saturated instance instead of spinning up more (toward the max of 10).

The sequence:

1. `min_instances: 0` let the service scale to zero when idle, so the next hit
   paid a cold start (observed: a 16.8s request plus "new process started").
2. A burst arrived. All four workers on the single instance were busy.
3. App Engine, unaware that concurrency was already exhausted, kept queuing
   requests to that instance rather than scaling out.
4. Queued requests exceeded the pending deadline and were aborted →
   `500`/`503` for everything, including `/`.
5. The instance cycled and the pattern repeated.

This was a **scale-out failure**, not resource exhaustion or an application
bug. The one healthy instance served every request it actually received.

## Fix

Three changes, all deployment configuration (no application code):

### 1. Cap per-instance concurrency (`.github/app.template.yaml`)

```yaml
automatic_scaling:
  min_instances: ${MIN_INSTANCES}
  max_instances: ${MAX_INSTANCES}
  max_concurrent_requests: 6
```

`max_concurrent_requests: 6` gives the scheduler an explicit ceiling, so it
scales out **before** an instance saturates. It is set intentionally *below*
the worker count (see change 3) so that ~2 workers of headroom absorb short
bursts while additional instances spin up, rather than packing an instance to
its limit before reacting.

### 2. Keep one instance warm (`.github/workflows/CD_production.yml`)

```
MIN_INSTANCES = 1   # was 0
```

A minimum of one always-on instance eliminates the cold-start pile-ups that
compounded the outage.

### 3. More concurrency per instance (`.github/workflows/CD_production.yml`)

```
gunicorn -w 8 -k uvicorn.workers.UvicornWorker main:app   # was -w 4
```

The F4 instance class (1 GB) comfortably runs eight workers, doubling the
throughput of each instance.

## Verification

After deploying, the live App Engine version reported:

- `maxConcurrentRequests: 6`
- `standardSchedulerSettings: { minInstances: 1, maxInstances: 10 }`

and request logs showed only `200`/`307` responses with **zero** blank-`instanceId`
`500`s (down from 279/300 in the failing window).

## Tuning notes

- `max_concurrent_requests` (6) is deliberately below the Gunicorn worker
  count (8). Raising it toward 8 packs each instance denser before scaling out
  (cheaper, less headroom); lowering it scales out more aggressively (more
  headroom, more instances). Keep it at or below the worker count — setting it
  above means requests queue on a busy instance instead of triggering
  scale-out, which is the exact failure this fixes.
- If heavy endpoints (large `limit` GeoJSON serializations) remain a load
  concern, consider capping `max_items` on those collections or paginating,
  independent of the scaling settings above.
```
