# App Engine OOM Instance Churn — Degradation and Fix

## Summary

On 2026-07-07 the production App Engine service `ocotillo-api` served **every**
request slowly, even at low traffic. The application was not returning errors —
requests eventually succeeded — but latency was uniformly high because the
single serving instance was being killed and restarted continuously. Each
request therefore tended to land on a process that was still cold-loading the
application.

The cause was memory exhaustion introduced by the previous scaling fix (see
[`app-engine-request-starvation.md`](app-engine-request-starvation.md)), which
raised the Gunicorn worker count from 4 to 8. Eight workers did not fit in the
F4 (1 GB) instance class. The fix raises the instance class to F4_1G (2 GB).

This is the direct sequel to the request-starvation outage: that fix cured the
scale-out failure but overshot on per-instance worker count for the instance's
memory.

## Symptoms

- Uniformly slow responses on all routes, **independent of traffic volume** —
  slow even when only one or two users were active.
- Not an outage: requests returned `200`, just slowly. No site-wide `500`/`503`
  (distinguishing this from the earlier starvation outage).
- Presented as "the API cold-starts for every user."

## Investigation

Because `min_instances` was `1`, one instance should always have been warm, so
uniform slowness at low traffic pointed at either (a) the warm instance
recycling, or (b) genuinely slow per-request work.

Per-request work was ruled out by reading `db/engine.py`: the SQLAlchemy engine
and connection pool are created once at module import
(`engine = init_connection_pool(connector)`) and reused across requests
(`pool_pre_ping=True`, `echo=False`). Requests do not re-establish connections,
so the slowness was not per-request connection setup.

That left instance recycling. Cloud Logging confirmed it. An initial query for
`"Exceeded soft memory limit"` returned nothing — that is the wrong phrase for
the App Engine **standard** environment. The correct signal is the message
below.

### Evidence (production, 3-hour window)

- **44** requests logged: *"the process that handled this request was found to
  be using too much memory and was terminated ... Consider setting a larger
  instance class in app.yaml."*
- **304** `Booting worker` lines — Gunicorn workers restarting continuously.
- **297** `SIGTERM` / **297** `was sent` — App Engine killing over-memory
  processes.
- **334** `shutting down` — instance/worker shutdown churn.
- Multiple *"This request caused a new process to be started ... loaded for the
  first time"* lines — cold loading requests hitting users directly.
- Live serving version confirmed as instance class **F4**, one instance,
  100% traffic.

A worker was being killed for memory roughly every four minutes, so the
"always-on" instance was effectively always cold.

## Root cause

The production entrypoint runs:

```
gunicorn -w 8 -k uvicorn.workers.UvicornWorker main:app
```

on instance class **F4 (1 GB)**. Each of the eight worker processes imports the
full application stack independently — SQLAlchemy, GeoAlchemy2, Shapely, the
Cloud SQL Python connector, and pygeoapi — with no `--preload`, so there is no
copy-on-write sharing between workers. Eight independent copies of that stack
exceeded 1 GB, so App Engine terminated worker processes for using too much
memory and started new ones, indefinitely.

The prior request-starvation fix deliberately raised `-w 4` → `-w 8` for more
per-instance throughput. On its own that change was reasonable, but it was not
paired with more memory, and 8 workers do not fit in F4.

## Fix

One change, deployment configuration only (`.github/app.template.yaml`):

```yaml
instance_class: F4_1G   # was F4
```

F4_1G provides 2 GB (same 2.4 GHz class), which comfortably holds eight workers
and their imports. This follows App Engine's own remediation message
("Consider setting a larger instance class").

The change deliberately preserves the scale-out tuning from the starvation fix
— `gunicorn -w 8`, `max_concurrent_requests: 6`, `min_instances: 1`,
`max_instances: 10` — so the earlier `500`/`503` starvation cannot recur.

### Alternatives considered

- **Reduce workers (`-w 8` → `-w 4`).** Would cut memory ~half at no cost, but
  requires also lowering `max_concurrent_requests` to stay at or below the
  worker count; otherwise the request-starvation failure returns. Retunes the
  balance the prior fix set. Rejected in favor of the lower-risk memory bump.
- **Add `--preload`.** Would share imports across forked workers, but the
  module-level SQLAlchemy engine / Cloud SQL `Connector` is created at import,
  and sharing a pool across forked processes is unsafe without a post-fork
  `engine.dispose()`. Not a one-line hotfix; rejected.

### Shared template note

`app.template.yaml` renders for all environments. Staging and testing run
`-w 4` and scale to zero (`MIN_INSTANCES=0`), so raising their class to F4_1G
grants harmless headroom at negligible idle cost. If per-environment instance
classes become desirable, template `instance_class` as `${INSTANCE_CLASS}` and
export it from each `CD_*` workflow, mirroring `MIN_INSTANCES` / `ENTRYPOINT`.

## Verification

After deploying `v1.1.5`, confirm on the live version:

```bash
gcloud app versions list --service=ocotillo-api \
  --project=waterdatainitiative-271000 \
  --hide-no-traffic --format='value(id, version.instanceClass)'
# expect: <version>  F4_1G
```

and confirm the over-memory terminations stop:

```bash
gcloud logging read \
  'resource.type="gae_app" AND resource.labels.module_id="ocotillo-api"
   AND "using too much memory"' \
  --project=waterdatainitiative-271000 --freshness=1h --format='value(timestamp)'
# expect: no results after the new version takes traffic
```

Request latency should drop to the warm-path baseline (~0.1 s for light
endpoints) once workers stop cycling.

## Tuning notes

- The correct App Engine **standard** memory-kill phrase for log searches is
  *"using too much memory and was terminated"*, **not** *"Exceeded soft memory
  limit"* (which is flex-environment wording). Searching the wrong phrase
  returns a false all-clear.
- Keep `max_concurrent_requests` (6) at or below the Gunicorn worker count (8);
  see the starvation doc for why.
- If memory again becomes tight after future dependency growth, the next levers
  are `--preload` with a post-fork pool dispose, or reducing worker count with a
  matching `max_concurrent_requests` reduction — before jumping another instance
  class.
```
