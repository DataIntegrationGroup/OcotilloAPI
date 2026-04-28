# ADR2: API Concurrency Fix Strategy

## Summary

This document describes a verified FastAPI concurrency issue in the API stack and recommends a two-phase remediation plan for maintainers.

The API uses synchronous SQLAlchemy sessions backed by `psycopg`. When those sessions are consumed from `async def` route handlers, blocking database work runs on the event loop thread if the handlers call synchronous ORM helpers directly. The lowest-risk immediate fix is to convert database-bound route handlers that do not perform asynchronous work into plain `def`. The longer-term fix is to introduce a real async SQLAlchemy stack and migrate the affected handlers and helpers incrementally.

## Problem

FastAPI supports synchronous generator dependencies such as `get_db_session()`. The issue is not the dependency shape itself. The issue is that the injected object is a synchronous SQLAlchemy `Session`, and any `async def` route that consumes it while executing synchronous ORM queries directly will block the event loop thread.

In this configuration, FastAPI runs the `async def` route body on the event loop thread. If that body performs blocking database I/O through the synchronous session, the worker cannot make progress on other requests assigned to that event loop until the database call returns. A slow well query can therefore delay unrelated lightweight requests handled by the same worker.

This is a concurrency problem, not a correctness problem. The endpoints can still return correct data while reducing throughput and responsiveness under load.

## Evidence In This Repo

- [`db/engine.py`](db/engine.py) creates `database_sessionmaker = sessionmaker(engine, expire_on_commit=False)` and `get_db_session()` yields a regular synchronous `Session`.
- [`db/engine.py`](db/engine.py) builds synchronous `postgresql+psycopg` engines for both the default PostgreSQL path and the Cloud SQL path, confirming that the active database layer is synchronous.
- [`core/dependencies.py`](core/dependencies.py) injects that session through `session_dependency`.
- [`services/well_details_helper.py`](services/well_details_helper.py) performs synchronous ORM operations such as `session.scalars(...).all()` and related query chains.
- [`api/thing.py`](api/thing.py) contains representative database-backed routes that pass the synchronous session into helper functions such as `get_db_things(...)` and `get_well_details_payload(...)`.
- [`api/asset.py`](api/asset.py) shows a contrasting safe pattern for non-database blocking work by wrapping synchronous GCS calls in `run_in_threadpool(...)`.
- The short-term fix described in this ADR converts database-bound routes from `async def` to `def` where they do not need `await`, but the helper/query layer remains synchronous until a real async session stack is introduced.

## Short-Term Fix

The short-term fix is to convert database-bound route handlers from `async def` to `def` when they do not actually perform asynchronous work.

This lets FastAPI offload the entire route function to a worker thread instead of running its synchronous database calls on the event loop thread. It does not require changing the current database engine, dependency, query helpers, or response schemas.

### Short-term implementation guidance

- Convert any route handler that:
  - receives `session: session_dependency`,
  - performs synchronous ORM work directly or through helpers, and
  - does not require `await` for other operations in the route body.
- Prioritize the highest-value endpoints first:
  - high-traffic list and detail endpoints,
  - endpoints known to run expensive joins or eager-loads,
  - endpoints that affect warmup or perceived application responsiveness.
- Keep route behavior unchanged:
  - do not change paths, status codes, payloads, or auth dependencies as part of this phase.
- Avoid mixed patterns:
  - do not leave a route as `async def` if it still calls synchronous SQLAlchemy code directly.
- Use `run_in_threadpool(...)` only when a route must remain `async def` for a separate reason, such as mixing in another async operation, and only for isolated blocking helpers rather than as a blanket wrapper for all DB access.

### Expected impact

- Lower risk than a full async migration.
- No intended HTTP contract changes.
- Better worker responsiveness because blocking DB work moves off the event loop thread.

## Long-Term Fix

The long-term fix is to add a real async database stack and migrate selected API areas to it incrementally.

This phase should introduce an explicit async path rather than trying to reuse the current synchronous dependency. Importing async SQLAlchemy primitives is not enough; the repo needs a working async engine, async sessionmaker, async dependency, and async query/helper layer for migrated endpoints.

### Long-term target architecture

- Add an `AsyncEngine` configured for the intended async driver.
- Add an `async_sessionmaker` that yields `AsyncSession` instances.
- Add a dedicated async dependency such as `get_async_db_session()` rather than overloading `get_db_session()`.
- Update migrated handlers and helper functions to use async database access:
  - `await session.execute(...)`
  - `await session.scalars(...)`
  - other `AsyncSession`-compatible patterns as needed

### Long-term migration guidance

- Migrate by subsystem, not all at once.
- Start with a bounded route/helper cluster where the query patterns are understood.
- Keep sync and async paths separate during migration to avoid ambiguous dependencies and accidental sync calls from async routes.
- Treat helper-layer migration as part of the work. Converting route signatures alone is insufficient if the helper functions still expect synchronous sessions.

### Non-goals and cautions

- Do not claim the repo already has a working async DB session path unless one is actually implemented and used.
- Do not treat “switch everything to async” as a trivial refactor.
- Do not mix `AsyncSession` route code with synchronous helper/query internals.

## Recommended Path

The recommended order is:

1. Convert database-bound `async def` routes that do not use `await` into plain `def`.
2. Validate behavior and measure the effect on responsiveness.
3. Introduce a dedicated async DB stack.
4. Migrate selected route/helper subsystems incrementally to `AsyncSession`.

This sequence delivers immediate concurrency improvement with limited risk, while preserving a clear path to a full async architecture later.

## Acceptance Criteria

### Short-term acceptance criteria

- Targeted API tests continue to pass after `async def` to `def` conversions.
- HTTP behavior is unchanged:
  - same routes,
  - same auth requirements,
  - same status codes,
  - same payload shapes.
- Concurrency smoke checks or request-timing instrumentation show that DB-heavy requests no longer block the event loop thread for that worker in the same way they do today.

### Long-term acceptance criteria

- Migrated endpoints pass the existing API test coverage for their subsystem.
- The async session lifecycle is correct for successful and failing requests.
- Migrated `async def` routes do not call synchronous session helpers.
- Before/after measurements are captured for latency and concurrency so the migration can be evaluated against real behavior rather than assumptions.

## Defaults And Assumptions

- This document is written for maintainers and assumes familiarity with FastAPI and SQLAlchemy internals.
- The document is self-contained and does not require code changes to be useful.
- The recommended short-term action is intentionally conservative and does not prescribe a file-by-file rollout sequence.
- The recommended long-term action is a staged migration, not a flag-day rewrite.
