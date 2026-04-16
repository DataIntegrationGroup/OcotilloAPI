# Services

This package contains application business logic, orchestration code, and
shared operational helpers.

General patterns:
- keep route handlers thin
- place reusable logic here instead of in CLI or API modules
- use high-volume DB loading patterns for bulk ingest paths

AEM service modules:
- `aem_ingest.py`: single-file ingest orchestration
- `aem_batch.py`: batch ingest from the mapping CSV
- `aem_db.py`: DB access helpers for AEM ingest
- `aem_loader.py`: bulk-load exports for AEM
- `aem_manifest.py`: Parquet/manifest/STAC exports for AEM
- `aem_provenance.py`: provenance and raw-file helper logic
- `aem_parsers/`: source-format parsing
