# API Monitoring Options for OcotilloAPI Production

**Purpose:** Evaluate open-source uptime and health-check monitoring tools for watching production deployments of OcotilloAPI (FastAPI + PostgreSQL/PostGIS), and — added in the 2026-07-07 revision — tools for a **public status page** so users and developers can see live service health.

**Focus:** Uptime and health checks — is the API reachable, is it responding within acceptable latency, and does its health endpoint report the database and dependencies as healthy — plus a public, subscribable status page. This document does not cover full APM/tracing platforms (SigNoz, Grafana Tempo, etc.), which are a heavier and separate decision.

**Date:** 2026-07-07

---

## What OcotilloAPI needs monitored

OcotilloAPI is a FastAPI service backed by PostgreSQL + PostGIS. A practical uptime/health monitor for this stack should cover:

- **Reachability** of the public API (HTTP/HTTPS status codes, TLS certificate validity/expiry).
- **A health endpoint** — expose a `/health` (and optionally `/health/db`) route in FastAPI that checks database connectivity and returns JSON like `{"status": "ok", "db": "ok"}`. All three tools below can assert against that JSON.
- **Response-time thresholds** — flag slow spatial queries before users notice.
- **Alerting** to a channel the team watches (email, Slack, PagerDuty).
- **A public status page** — a page users and developers can visit to see current uptime, incidents, and planned maintenance, ideally with email/RSS/webhook subscriptions.
- **Self-hostable** alongside the existing Docker Compose stack, and ideally versioned in the repo.

> **Probe independence.** A status page exists to be trustworthy *when the service is down*. If the monitor runs inside the same GCP project/App Engine service it watches, a platform-level outage takes the status page down with it (correlated failure). Run the probe from an **external vantage** — a hosted/SaaS checker, or a self-hosted probe on separate infrastructure — regardless of which tool below is chosen.

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

## Option 4 — OpenStatus

**License:** AGPL-3.0 · **Language:** TypeScript (Next.js) · **Repo:** github.com/openstatusHQ/openstatus

OpenStatus is a **status-page-first** platform that combines synthetic uptime monitoring, public status pages, and incident/maintenance communication in one product. Unlike the three options above — where a status page is either a side feature (Uptime Kuma, Gatus) or absent (Blackbox Exporter) — the public status page is OpenStatus's primary deliverable. Available as managed SaaS or fully self-hosted.

**Relevant capabilities**

- HTTP/HTTPS (REST/GraphQL) and TCP monitoring with assertions on status code, response time, headers, and response body — maps onto the existing `/health` route (`core/app.py`, returns `{"status": "ok", "version": ...}`).
- **Public status page** with custom domains, branded themes, timestamped incident reports, and scheduled maintenance windows. Automatic status updates during incidents (no manual toggling).
- **Subscriber notifications** on the status page: email, RSS/Atom, and webhooks — so users and developers self-subscribe to updates.
- **Monitoring as code**: YAML config, a Terraform provider, a CLI, and GitHub Actions integration — checks live in the repo, consistent with this project's release-please / templated-`app.yaml` / `geoserver_iac/` Terraform habits.
- Alerts via Slack, Discord, PagerDuty, email, and webhooks. A RESTful (OpenAPI) API for automation.
- SaaS probes run from 28 regions across 3 cloud providers; self-hosting supports private probe locations behind a firewall.
- Self-host ships as Docker Compose. A **lightweight status-page-only** mode runs just four services (database, migration runner, dashboard, status page) for teams that only want the public page.

**Fit for OcotilloAPI**

The best fit specifically for the "users and developers can see status" goal, because the public status page is first-class rather than bolted on, and because monitoring-as-code (YAML + Terraform) matches how this repo already manages deployment config. Lowest-effort path: the SaaS free tier watching `https://<prod-host>/health`, published to a custom-domain status page — zero infrastructure and an external probe vantage by default.

**Trade-offs**

- **AGPL-3.0** copyleft. Fine for internal self-hosting; only a concern if the code is modified *and redistributed*.
- SaaS free tier is limited to **one monitor, one status page, 10-minute checks**; more monitors or faster intervals start at ~$30/month. Self-hosting removes these limits but requires running (and keeping independent) the stack.
- Self-hosting the probe on the same infrastructure as OcotilloAPI reintroduces the correlated-failure problem noted above — keep the probe external, or use SaaS.
- Newer and smaller-community than Uptime Kuma; maintained by a small bootstrapped team.

---

## Comparison

| Criterion | Uptime Kuma | Gatus | Blackbox Exporter | OpenStatus |
|---|---|---|---|---|
| License | MIT | Apache 2.0 | Apache 2.0 | AGPL-3.0 |
| Configuration | Web UI (stored in DB) | YAML (config-as-code) | YAML + Prometheus config | YAML / Terraform / UI |
| JSON health-body assertion | Yes (JSON query) | Yes (`[BODY]` conditions) | Regex on body | Yes (body assertions) |
| TLS expiry checks | Yes | Yes | Yes | Yes |
| Response-time thresholds | Yes | Yes | Yes (via Prometheus rules) | Yes |
| Public status page | Yes | Basic | No | **Yes (first-class)** |
| Status-page subscriptions | Limited | No | No | Email / RSS / webhook |
| Built-in dashboard | Yes (rich + status page) | Yes (lightweight) | No (needs Grafana) | Yes (status page + dashboard) |
| Alerting | Many integrations built in | Many integrations built in | Via Alertmanager | Slack/Discord/PagerDuty/email/webhook |
| Setup effort | Low (1 container) | Low (1 container) | High (full stack) | Low (SaaS) / Medium (self-host) |
| GitOps / versioned config | No (community tooling) | Yes (native) | Yes | Yes (YAML + Terraform) |
| Hosted SaaS option | No | No | No | Yes (free tier + paid) |
| Best when… | Want a UI + status page fast | Want config in the repo | Already run Prometheus | Want a public status page + config-as-code |

---

## Recommendation

The goal has two parts: (a) internal uptime/health monitoring and alerting, and (b) a **public status page** for users and developers. The right pick depends on which dominates.

**If the public status page is the priority (the current goal): OpenStatus.** The status page is first-class — custom domain, incident timeline, maintenance windows, and email/RSS/webhook subscriptions — and monitoring-as-code (YAML + Terraform) matches this repo's existing config-as-code habits. Fastest path: the **SaaS free tier** watching `https://<prod-host>/health`, published to a custom-domain status page. Zero infrastructure, and the probe runs from an external vantage by default (satisfying the probe-independence requirement). Upgrade to a paid tier or self-host only when more monitors or sub-10-minute intervals are needed.

**If config-as-code monitoring/alerting matters more than the public page: Gatus.** One repo-committed `config.yaml`, one container, JSON health assertions, flap-resistant alerting. Its status page is thinner than OpenStatus's, so pair it with OpenStatus (or promote OpenStatus) if the public page becomes central.

**If a friendly point-and-click UI is the priority: Uptime Kuma.** Quickest UI-driven setup and a decent status page, at the cost of no native GitOps.

**Blackbox Exporter** remains the choice only if (or once) OcotilloAPI adopts Prometheus for broader infrastructure metrics — then fold endpoint monitoring into that stack rather than running a separate tool. It has no status page of its own.

A reasonable starting move for the stated goal: stand up **OpenStatus** (SaaS free tier to start) monitoring the existing `/health` route, publish a public status page on a custom domain, and commit the monitor definition (YAML/Terraform) to the repo. Keep the probe external to GCP so the page stays up during a platform outage.

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
- [OpenStatus — official site](https://www.openstatus.dev/)
- [OpenStatus — GitHub](https://github.com/openstatusHQ/openstatus)
- [OpenStatus — self-hosting guide](https://docs.openstatus.dev/guides/self-hosting-openstatus/)
- [OpenStatus — self-host status page only (lightweight)](https://docs.openstatus.dev/guides/self-host-status-page-only/)
