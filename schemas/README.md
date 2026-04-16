# Schemas

This package contains Pydantic models and validation helpers used by Ocotillo.

Highlights:
- request/response schemas for API and CLI workflows
- shared validation utilities
- AEM ingest schemas in `aem.py`

For AEM specifically, `schemas/aem.py` defines:
- ingest configuration
- source-format and processing enums
- row-level validation helpers for parsed sounding data
