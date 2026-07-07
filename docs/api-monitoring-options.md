# API Monitoring Options for OcotilloAPI Production

**Purpose:** Evaluate three open-source uptime and health-check monitoring tools for watching production deployments of OcotilloAPI (FastAPI + PostgreSQL/PostGIS).

**Focus:** Uptime and health checks — is the API reachable, is it responding within acceptable latency, and does its health endpoint report the database and dependencies as healthy. This document does not cover full APM/tracing platforms (SigNoz, Grafana Tempo, etc.), which are a heavier and separate decision.

**Date:** 2026-07-07

---

## What OcotilloAPI needs monitored

OcotilloAPI is a FastAPI service backed by PostgreSQL + PostGIS. A practical uptime/health monitor for this stack should cover:

- **Reachability** of the public API (HTTP/HTTPS status codes, TLS certificate validity/expiry).
- **A health endpoint** — expose a `/health` (and optionally `/health/db`) route in FastAPI that checks database connectivity and returns JSON like `{"status": "ok", "db": "ok"}`. All three tools below can assert against that JSON.
- **Response-time thresholds** — flag slow spatial queries before users notice.
- **Alerting** to a channel the team watches (email, Slack, PagerDuty).
- **Self-hostable** alongside the existing Docker Compose stack, and ideally versioned in the repo.

A recommended FastAPI health route to monitor:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import text

router = APIRouter()

@router.get("/health")
async def health(session=Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
```

---

## Option 1 — Uptime Kuma

**License:** MIT · **Language:** Node.js/Vue · **Repo:** github.com/louislam/uptime-kuma (~76k+ GitHub stars — the most popular self-hosted uptime monitor)

Uptime Kuma is a UI-driven, self-hosted uptime monitor. You add and configure monitors through a polished web dashboard rather than a config file.

**Relevant capabilities**

- Monitor types include HTTP/HTTPS, TCP port, ping, DNS, keyword-in-response, **HTTP(S) JSON query**, database checks, and Docker containers.
- HTTP monitor checks the status code, can assert a **keyword** or a **JSON query** against the response body (ideal for asserting `"db": "ok"` from the health route), and warns on certificate expiry within a configurable threshold.
- Built-in status pages, per-monitor history/uptime %, and a large set of notification integrations (Slack, email/SMTP, Telegram, Discord, PagerDuty, webhooks, and many more).
- v2.0 (Oct 2025) added MariaDB backend support, rootless Docker images, refreshed UI. v2.1 (Feb 2026) added Globalping worldwide probes and domain-expiry monitoring.

**Fit for OcotilloAPI**

Fastest path to "is the API up and is the DB healthy." Drops into the existing Docker Compose stack as one container, and the JSON-query monitor maps directly onto a FastAPI `/health` response. Best when the team wants a friendly UI and public status page with minimal setup.

**Trade-offs**

- Config lives in the app's own database, not in the repo — no native config-as-code/GitOps (community tools like the `uptime-kuma-api` Python package or `uptime-kuma-web-api` can script setup, but it is not first-class).
- No official REST API; automation goes through the Socket.IO API.
- Single-instance architecture; not built for horizontally-scaled HA.

---

## Option 2 — Gatus

**License:** Apache 2.0 · **Language:** Go · **Repo:** github.com/TwiN/gatus

Gatus is a lightweight, developer-oriented health dashboard where every monitored endpoint, condition, and alert rule is declared in a **YAML file**. That makes it a natural fit for GitOps — monitoring changes become versioned commits.

**Relevant capabilities**

- Probes HTTP, TCP, ICMP, DNS, WebSocket, SSH, TLS, and STARTTLS endpoints on a schedule.
- Declarative **conditions** on status code, response time, response body (including JSON assertions, e.g. `[BODY].db == ok`), IP, and TLS certificate expiration.
- `failure-threshold` / `success-threshold` settings prevent alert flapping from intermittent blips.
- Alerting out of the box: Slack, Mattermost, PagerDuty, Twilio, Google Chat, Teams, Messagebird, plus custom providers.
- Built-in web dashboard with per-endpoint status, response-time history, and uptime % — no Grafana required for basic visualization.

**Fit for OcotilloAPI**

Strong match for a team that already versions infrastructure. A single `config.yaml` lives in the repo next to OcotilloAPI, defining checks against `/health`, asserting the JSON body and a response-time ceiling, and firing alerts after N consecutive failures. Lightweight Go binary/container, low resource use.

Example condition set:

```yaml
endpoints:
  - name: ocotillo-api-health
    url: "https://api.example.org/health"
    interval: 60s
    conditions:
      - "[STATUS] == 200"
      - "[BODY].db == ok"
      - "[RESPONSE_TIME] < 500"
    alerts:
      - type: slack
        failure-threshold: 3
        success-threshold: 2
```

**Trade-offs**

- No point-and-click UI for adding monitors — everything is YAML (a feature for engineers, friction for non-technical stakeholders).
- Status-page/incident features are lighter than Uptime Kuma's.

---

## Option 3 — Prometheus Blackbox Exporter

**License:** Apache 2.0 · **Language:** Go · **Repo:** github.com/prometheus/blackbox_exporter (official Prometheus / CNCF component)

The Blackbox Exporter probes endpoints externally and exposes the results as **Prometheus metrics**. It is the production-grade, standards-based choice — but it is a component, not a standalone product: it assumes (or introduces) a Prometheus + Alertmanager stack, usually with Grafana for dashboards.

**Relevant capabilities**

- Probes over HTTP, HTTPS, DNS, TCP, ICMP, and gRPC.
- HTTP probe defaults to GET expecting 2xx; configurable for other methods, expected status codes, **basic/bearer auth**, custom headers, body matching (regex on response), and proxies.
- Emits metrics such as `probe_success`, `probe_duration_seconds`, `probe_http_status_code`, and `probe_ssl_earliest_cert_expiry` (TLS expiry timestamp).
- Alerting via Prometheus alerting rules → Alertmanager (routing, grouping, silencing, dedup) to Slack, PagerDuty, email, etc.
- Multi-target / multi-region probing and long-term metric retention when paired with the Prometheus stack.

**Fit for OcotilloAPI**

Best long-term fit **if** OcotilloAPI already runs, or plans to run, Prometheus for infrastructure metrics. Then endpoint uptime, latency, and cert expiry become just more series alongside app and host metrics, with unified Grafana dashboards and Alertmanager routing. Body-regex matching can assert the health-endpoint payload.

**Trade-offs**

- Heaviest setup by far: Blackbox Exporter + Prometheus + Alertmanager (+ Grafana) to reach parity with what Uptime Kuma or Gatus give in one container.
- No built-in status page or friendly UI on its own.
- Overkill if uptime/health is the only goal and there is no existing Prometheus footprint.

---

## Comparison

| Criterion | Uptime Kuma | Gatus | Blackbox Exporter |
|---|---|---|---|
| License | MIT | Apache 2.0 | Apache 2.0 |
| Configuration | Web UI (stored in DB) | YAML (config-as-code) | YAML + Prometheus config |
| JSON health-body assertion | Yes (JSON query) | Yes (`[BODY]` conditions) | Regex on body |
| TLS expiry checks | Yes | Yes | Yes |
| Response-time thresholds | Yes | Yes | Yes (via Prometheus rules) |
| Built-in dashboard | Yes (rich + status page) | Yes (lightweight) | No (needs Grafana) |
| Alerting | Many integrations built in | Many integrations built in | Via Alertmanager |
| Setup effort | Low (1 container) | Low (1 container) | High (full stack) |
| GitOps / versioned config | No (community tooling) | Yes (native) | Yes |
| Best when… | Want a UI + status page fast | Want config in the repo | Already run Prometheus |

---

## Recommendation

For OcotilloAPI's stated goal — uptime and health-check monitoring of a production FastAPI + PostGIS service — the pragmatic ranking:

1. **Gatus** if the team values keeping monitoring configuration versioned in the repo alongside the code (consistent with this project's alembic/config-as-code habits). One YAML file, one container, JSON health assertions, and flap-resistant alerting.
2. **Uptime Kuma** if a friendly UI and a public/internal status page matter more than GitOps, and the team wants the quickest possible setup.
3. **Blackbox Exporter** only if (or once) OcotilloAPI adopts Prometheus for broader infrastructure metrics — then fold endpoint monitoring into that stack rather than running a separate tool.

A reasonable starting move: add a `/health` route to FastAPI that verifies PostGIS connectivity, then stand up **Gatus** as a container in the existing Docker Compose stack with a repo-committed `config.yaml`. Revisit Blackbox Exporter if/when a Prometheus stack is introduced.

---

## Sources

- [Uptime Kuma — GitHub](https://github.com/louislam/uptime-kuma)
- [Uptime Kuma — official site](https://uptimekuma.org/)
- [Uptime Kuma: Self-Hosted Uptime Monitoring for Servers and APIs](https://trivox.sh/blog/content/uptime-kuma-self-hosted-monitoring/)
- [Gatus — GitHub](https://github.com/TwiN/gatus)
- [Gatus: A Complete Guide to Self-Hosted Service Monitoring and Status Pages](https://www.blog.brightcoding.dev/2025/07/26/gatus-a-complete-guide-to-self-hosted-service-monitoring-and-status-pages/)
- [Gatus vs Uptime Kuma: A Detailed Comparison (2026)](https://openalternative.co/compare/gatus/vs/uptime-kuma)
- [Prometheus Blackbox Exporter — GitHub](https://github.com/prometheus/blackbox_exporter)
- [Prometheus Blackbox Exporter: Ultimate Guide (SolarWinds)](https://www.solarwinds.com/blog/prometheus-blackbox-exporter)
- [How to Use Alertmanager and Blackbox Exporter to Monitor Your Web Server (DigitalOcean)](https://www.digitalocean.com/community/tutorials/how-to-use-alertmanager-and-blackbox-exporter-to-monitor-your-web-server-on-ubuntu-16-04)
