# AEM Assets

This directory is for AEM operational assets and reference material that are
not part of the core app runtime.

Contents:
- `aem_gcs_mapper.py`: mapping/planning utility for source files and GCS paths
- `aem_migrate.py`: operational migration helper
- `gcs_path_mapping.csv`: reviewed ingest/migration mapping input
- migration logs and summaries generated during operational runs

Core AEM runtime code does not live here anymore. Use the main app packages for
that work:
- `db/aem.py`
- `schemas/aem.py`
- `services/aem_ingest.py`
- `services/aem_batch.py`
- `services/aem_parsers/`
- `cli/aem.py`
