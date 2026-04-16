"""
aem_ingest.parsers — Format-specific parsers for AEM inversion files.

Each parser is a pure function: filepath in → canonical DataFrame out.
No database connections, no GCS clients, no side effects.  This makes
them safe to call in notebooks (Ahsan, Stacy) and in unit tests.
"""

from aem_ingest.parsers.detect import detect_format, extract_flight_id  # noqa: F401
from aem_ingest.parsers.bylayer import parse_bylayer  # noqa: F401
from aem_ingest.parsers.seogi import parse_seogi_rho  # noqa: F401
from aem_ingest.parsers.agf import parse_agf_lci  # noqa: F401
