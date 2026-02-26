# API

This directory contains FastAPI route modules grouped by resource/domain.

## Structure

- One module per domain (for example `thing.py`, `contact.py`, `observation.py`)
- OGC API - Features is mounted via `pygeoapi` (see `core/pygeoapi.py`)

## Guidelines

- Keep endpoints focused on transport concerns (request/response, status codes).
- Put transfer/business logic in service or transfer modules.
- Ensure response schemas match `schemas/` definitions.

## Running locally

Use project entrypoint from repo root (see top-level README for full setup).
